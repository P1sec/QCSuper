#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/socket.h>
#include <poll.h>
#include <string.h>
#include <arpa/inet.h>
#include <pthread.h>
#include <errno.h>

/**
 * This C utility will forward Qualcomm Diag data over TCP to /dev/diag, running
 * on an Android host.
 * 
 * Bi-directional format on the TCP socket: [ Raw data ]
 * 
 * Input format on the /dev/diag device: [ (int) USER_SPACE_DATA_TYPE constant ] [ (int) MDM constant ] [ Raw data ]
 * Output format on the /dev/diag device: [ (int) USER_SPACE_DATA_TYPE constant ] [ (int) MDM constant ] [ (int) Number of buffers ] { [ (int) Buffer size ] [ Raw data ] .. }
 * 
 * Related code from Android codebase:
 * - /dev/diag driver for Android 6.0 https://android.googlesource.com/kernel/msm.git/+/android-6.0.0_r0.9/drivers/char/diag
 * 
 * Similar work:
 * - diag_revealer.c from MobileInsight https://github.com/mobile-insight/mobileinsight-mobile/blob/master/diag_revealer/qcom/jni/diag_revealer.c
 * - diag-helper.c from SnoopSnitch https://github.com/BramBonne/snoopsnitch-pcapinterface/blob/master/SnoopSnitch/jni/diag-helper.c
 * 
 * Note: large parts of the recent versions of this file have been taken from
 * "diag_revealer.c" mentioned above, in order to guarantee compatibility with
 * recent Android devices through leveraging calling the "libdiag.so" library
 * through "libdl" when required.
 * 
 * Extra credits taken from the original "diag_revealer.c" source:
 * 
 * > Author: Jiayao Li, Yuanjie Li, Haotian Deng
 * > Changes:
 * >   Ruihan Li: Probe ioctl argument length.
 * >              Fix libdiag.so logging switching.
 * >              Add Android 10 support.
 */

#include <assert.h>
#include <endian.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <signal.h>
#include <unistd.h>
#include <string.h>
#include <errno.h>
#include <sys/ioctl.h>
#include <sys/time.h>
#include <sys/resource.h>
#include <sys/mman.h>
#include <dlfcn.h>

#define QCSUPER_TCP_PORT 43555

#define BUFFER_LEN 1024 * 1024 * 10
#define FDS_LEN 4096

#define USER_SPACE_DATA_TYPE 0x00000020

#define QCSUPER_SIZE_FIELD_SIZE 4
#define DIAG_DATATYPE_FIELD_SIZE 4

#define  LOGE(...)  fprintf(stderr, __VA_ARGS__)
#define  LOGW(...)  fprintf(stderr, __VA_ARGS__)
#define  LOGD(...)  fprintf(stderr, __VA_ARGS__)
#define  LOGI(...)  fprintf(stderr, __VA_ARGS__)

static void* (*real_pthread_create)(pthread_t*, const pthread_attr_t*, void *(*) (void *), void *) = NULL;

typedef int (*D_FUNC)(int, int);
typedef signed int (*I_FUNC)();
typedef int (*F_FUNC)(int);
typedef int (*R_FUNC)(const char *);

#define LIBDIAG_TMPPATH "/data/local/tmp/libdiag.so"

/*
 * MDM VS. MSM
 * Reference: https://android.googlesource.com/kernel/msm.git/+/android-6.0.0_r0.9/include/linux/diagchar.h
 */
enum remote_procs {
    MSM = 0,
    MDM = 1,
    MDM2 = 2,
    QSC = 5,
};

/* Raw binary data type
 * Reference: https://android.googlesource.com/kernel/msm.git/+/android-6.0.0_r0.9/include/linux/diagchar.h
 */
#define MSG_MASKS_TYPE        0x00000001
#define LOG_MASKS_TYPE        0x00000002
#define EVENT_MASKS_TYPE    0x00000004
#define PKT_TYPE        0x00000008
#define DEINIT_TYPE        0x00000010
#define USER_SPACE_DATA_TYPE    0x00000020
#define DCI_DATA_TYPE        0x00000040
#define CALLBACK_DATA_TYPE    0x00000080
#define DCI_LOG_MASKS_TYPE    0x00000100
#define DCI_EVENT_MASKS_TYPE    0x00000200
#define DCI_PKT_TYPE        0x00000400

/* IOCTL commands for diagnostic port
 * Reference: https://android.googlesource.com/kernel/msm.git/+/android-6.0.0_r0.9/include/linux/diagchar.h
 */
#define DIAG_IOCTL_SWITCH_LOGGING    7
#define DIAG_IOCTL_LSM_DEINIT        9
#define DIAG_IOCTL_DCI_REG        23
#define DIAG_IOCTL_DCI_INIT        20
#define DIAG_IOCTL_DCI_DEINIT        21
#define DIAG_IOCTL_DCI_CLEAR_LOGS    28
#define DIAG_IOCTL_DCI_CLEAR_EVENTS    29
#define DIAG_IOCTL_REMOTE_DEV        32
#define DIAG_IOCTL_VOTE_REAL_TIME    33
#define DIAG_IOCTL_GET_REAL_TIME    34
#define DIAG_IOCTL_PERIPHERAL_BUF_CONFIG    35
#define DIAG_IOCTL_PERIPHERAL_BUF_DRAIN        36

#define MEMORY_DEVICE_MODE        2
#define CALLBACK_MODE            6
#define TTY_MODE            8

/*
 * NEXUS-6-ONLY IOCTL
 * Reference: https://github.com/MotorolaMobilityLLC/kernel-msm/blob/kitkat-4.4.4-release-victara/include/linux/diagchar.h
 */
#define DIAG_IOCTL_OPTIMIZED_LOGGING        35
#define DIAG_IOCTL_OPTIMIZED_LOGGING_FLUSH    36

/*
 * Buffering mode
 * Reference: https://android.googlesource.com/kernel/msm.git/+/android-6.0.0_r0.9/include/linux/diagchar.h
 */
#define DIAG_BUFFERING_MODE_STREAMING    0
#define DIAG_BUFFERING_MODE_THRESHOLD    1
#define DIAG_BUFFERING_MODE_CIRCULAR    2
#define DEFAULT_LOW_WM_VAL    15
#define DEFAULT_HIGH_WM_VAL    85
#define NUM_SMD_DATA_CHANNELS    4
#define NUM_SMD_CONTROL_CHANNELS NUM_SMD_DATA_CHANNELS

#define MODEM_DATA        0
#define LAST_PERIPHERAL        3

/*
 * Structures for DCI client registration
 * Reference: https://android.googlesource.com/kernel/msm.git/+/android-6.0.0_r0.9/drivers/char/diag/diag_dci.h
 */
#define DCI_LOG_MASK_SIZE        (16 * 514)
#define DCI_EVENT_MASK_SIZE        512
struct diag_dci_reg_tbl_t {
    int client_id;
    uint16_t notification_list;
    int signal_type;
    int token;
} __packed;

/*
 * Android 10.0: switch_logging_mode structure
 * Reference: https://android.googlesource.com/kernel/msm.git/+/android-10.0.0_r0.87/drivers/char/diag/diagchar.h
 * Android 11.0.0 (RD1A.201105.003.C1)
 * https://android.googlesource.com/kernel/msm.git/+/refs/tags/android-11.0.0_r0.27/drivers/char/diag/diagchar.h
 */
struct diag_logging_mode_param_t_q {
    uint32_t req_mode;
    uint32_t peripheral_mask;
    uint32_t pd_mask;
    uint8_t mode_param;
    uint8_t diag_id;
    uint8_t pd_val;
    uint8_t reserved;
    int peripheral;
    int device_mask;
} __packed;
#define DIAG_MD_LOCAL        0
#define DIAG_MD_LOCAL_LAST    1
#define DIAG_MD_BRIDGE_BASE    DIAG_MD_LOCAL_LAST
#define DIAG_MD_MDM        (DIAG_MD_BRIDGE_BASE)
#define DIAG_MD_MDM2        (DIAG_MD_BRIDGE_BASE + 1)
#define DIAG_MD_BRIDGE_LAST    (DIAG_MD_BRIDGE_BASE + 2)

struct diag_con_all_param_t {
    uint32_t diag_con_all;
    uint32_t num_peripherals;
    uint32_t upd_map_supported;
};
#define DIAG_IOCTL_QUERY_CON_ALL    40

/*
 * Android 9.0: switch_logging_mode structure
 * Reference: https://android.googlesource.com/kernel/msm.git/+/android-9.0.0_r0.31/drivers/char/diag/diagchar.h
 */
struct diag_logging_mode_param_t_pie {
    uint32_t req_mode;
    uint32_t peripheral_mask;
    uint32_t pd_mask;
    uint8_t mode_param;
    uint8_t diag_id;
    uint8_t pd_val;
    uint8_t reserved;
    int peripheral;
} __packed;

/*
 * Android 7.0: switch_logging_mode structure
 * Reference: https://android.googlesource.com/kernel/msm.git/+/android-7.1.0_r0.3/drivers/char/diag/diagchar.h
 */
struct diag_logging_mode_param_t {
    uint32_t req_mode;
    uint32_t peripheral_mask;
    uint8_t mode_param;
} __packed;
#define DIAG_CON_APSS        (0x0001)    /* Bit mask for APSS */
#define DIAG_CON_MPSS        (0x0002)    /* Bit mask for MPSS */
#define DIAG_CON_LPASS        (0x0004)    /* Bit mask for LPASS */
#define DIAG_CON_WCNSS        (0x0008)    /* Bit mask for WCNSS */
#define DIAG_CON_SENSORS    (0x0010)    /* Bit mask for Sensors */
#define DIAG_CON_NONE        (0x0000)    /* Bit mask for No SS*/
#define DIAG_CON_ALL        (DIAG_CON_APSS | DIAG_CON_MPSS \
                | DIAG_CON_LPASS | DIAG_CON_WCNSS \
                | DIAG_CON_SENSORS)

/*
 * Structures for ioctl
 * Reference: https://android.googlesource.com/kernel/msm.git/+/android-6.0.0_r0.9/drivers/char/diag/diagchar_core.c
 */

struct diag_buffering_mode_t {
    uint8_t peripheral;
    uint8_t mode;
    uint8_t high_wm_val;
    uint8_t low_wm_val;
} __packed;

#define DIAG_PROC_DCI            1
#define DIAG_PROC_MEMORY_DEVICE        2

struct real_time_vote_t {
    uint16_t proc;
    uint8_t real_time_vote;
};

struct real_time_query_t {
    int real_time;
    int proc;
} __packed;

/*
 * DCI structures
 */
struct diag_dci_client_tbl {
    struct task_struct *client;
    uint16_t list; /* bit mask */
    int signal_type;
    unsigned char dci_log_mask[DCI_LOG_MASK_SIZE];
    unsigned char dci_event_mask[DCI_EVENT_MASK_SIZE];
    unsigned char *dci_data;
    int data_len;
    int total_capacity;
    int dropped_logs;
    int dropped_events;
    int received_logs;
    int received_events;
};

/*
 * Default logging mode and buffer
 * Reference: https://android.googlesource.com/kernel/msm.git/+/android-6.0.0_r0.9/drivers/char/diag/diag_dci.h
 */

// int mode = CALLBACK_MODE;    // Logging mode
static int mode = MEMORY_DEVICE_MODE;    // logging mode
static uint16_t use_mdm = 0; // MSM (0) or not
static int client_id;    // DCI client ID (allocated by diag driver)
static int diag_fd; // file descriptor to /dev/diag

struct pollfd fds[FDS_LEN] = { 0 };
int number_fds = 0;

pthread_mutex_t fdset_mutex = PTHREAD_MUTEX_INITIALIZER;

void error(char* arg) {
    perror(arg);
    exit(1);
}

void* diag_read_thread(void* arg) {
    char* diag_buffer = malloc(BUFFER_LEN);

    while(1) {
        int bytes_read = read(diag_fd, diag_buffer, BUFFER_LEN);
        
        if (bytes_read < 4) error("read");
        
        if(*(unsigned int*) diag_buffer != USER_SPACE_DATA_TYPE) continue;
        
        /*for(int i = 0; i < bytes_read; i++) {
            printf("%02x ", diag_buffer[i]);
        }
        printf("\n");*/
        
        // Broadcast each received message
        
        pthread_mutex_lock(&fdset_mutex);
        
        unsigned int nb_msgs = *(unsigned int*)(diag_buffer + 4);
        
        char* send_buffer = diag_buffer + 8;
        
        for(int i = 0; i < nb_msgs; i++) {
            
            if(send_buffer < diag_buffer || send_buffer + (use_mdm ? 8 : 4) > diag_buffer + bytes_read) {
                goto wrong_length;
            }
            
            if(use_mdm && *(int*) send_buffer == -1) {
                send_buffer += 4;
            }
            
            int msg_length = *(unsigned int*) send_buffer;
            send_buffer += 4;
            
            if(send_buffer + msg_length > diag_buffer + bytes_read) {
                goto wrong_length;
            }
            
            for(int j = 1; j < number_fds; j++) {
                write(fds[j].fd, send_buffer, msg_length);
            }
            
            send_buffer += msg_length;
            continue;

wrong_length:
            fprintf(stderr, "Error: wrong length received from diag\n");
            exit(1);
        }
        
        pthread_mutex_unlock(&fdset_mutex);
    }
}

/*
 * Explicitly probe the length of the argument that ioctl(diag_fd, req, ...) takes.
 *
 * Assumptions:
 *  1. The length is fixed.
 *  2. The insufficient length is the only reason to make ioctl(diag_fd, req, ...)
 *     fail and set errno to EFAULT.
 *  3. The argument filled with 0x3f won't cause unrecoverable errors, or
 *     interfere with what we're going to do next.
 */
static ssize_t
probe_ioctl_arglen (int req, size_t maxlen)
{
    size_t pagesize = sysconf(_SC_PAGESIZE);
    char *p;
    size_t len;

    if (maxlen > pagesize) {
        LOGE("probe_ioctl_arglen: maxlen > pagesize is not implemented\n");
        return -1;
    }

    p = mmap(NULL, pagesize * 2, PROT_READ | PROT_WRITE, MAP_ANONYMOUS | MAP_PRIVATE, 0, 0);
    if (p == MAP_FAILED) {
        LOGE("probe_ioctl_arglen: mmap fails (%s)\n", strerror(errno));
        return -1;
    }
    p += pagesize;
    munmap(p, pagesize);
    memset(p - maxlen, 0x3f, maxlen);

    for (len = 0; len <= maxlen; ++len) {
        if (ioctl(diag_fd, req, p - len) >= 0)
            break;
        if (errno != EFAULT)
            break;
    }
    munmap(p - pagesize, pagesize);
    return len;
}

/*
 * Calling functions into libdiag.so will create several threads. For example,
 * in diag_switch_logging, three threads (disk_write_hdl, qsr4_db_parser_thread_hdl,
 * db_write_thread_hdl) will be created. But actually we don't need them at all.
 * Meanwhile we cannot call dlclose when these useless threads are still alive.
 * So the following fake pthread_create is used to prevent them from being created.
 *
 * Note this fake pthread_create may cause some unexpected side effects on another
 * untested version of libdiag.so. If so, futher modification is needed.
 *
 * Tested devices:
 *   Xiaomi Mi 5S            Android 7.1.2
 *   Huawei Nexus 6P         Android 8.0.0
 *   Xiaomi Redmi Note 8     Android 10.0.0
 *   Samsung Galaxy A90 5G   Android 10.0.0
 */
int
pthread_create (pthread_t *thread, const pthread_attr_t *attr,
                void *(*start_routine)(void *), void *arg) {
    *thread = 1;
    return 0;
}

static int
__enable_logging_libdiag (int mode)
{
    static char libdiag_copycmd[256];
    const char *LIB_DIAG_PATH[] = {
        "/system/vendor/lib64/libdiag.so",
        "/system/vendor/lib/libdiag.so",
    };

    int ret;
    const char *err;
    void *handle;
    void (*diag_switch_logging)(int, const char *);
    int *diag_fd_ptr;
    int *logging_mode;

    /*
     * "Starting in Android 7.0, the system prevents apps from dynamically linking against
     * non-NDK libraries, which may cause your app to crash."
     * Reference: https://developer.android.com/about/versions/nougat/android-7.0-changes#ndk
     *
     * Copy it into LIBDIAG_TMPPATH and load it.
     */
    handle = NULL;
    for (unsigned int i = 0; i < sizeof(LIB_DIAG_PATH) / sizeof(LIB_DIAG_PATH[0]) && !handle; ++i) {
        sprintf(libdiag_copycmd, "su -c cp %s " LIBDIAG_TMPPATH "\n", LIB_DIAG_PATH[i]);
        system(libdiag_copycmd);
        handle = dlopen(LIBDIAG_TMPPATH, RTLD_NOW);
        if (!handle)
            LOGE("dlopen %s failed (%s)\n", LIB_DIAG_PATH[i], dlerror());
        // else
        //     LOGI("dlopen %s succeeded\n", LIB_DIAG_PATH[i]);
    }
    if (!handle)
        return -1;

    // Note diag_switch_logging does NOT have a return value in general.
    err = "diag_switch_logging";
    diag_switch_logging = (void (*)(int, const char *)) dlsym(handle, "diag_switch_logging");
    if (!diag_switch_logging)
        goto fail;
    err = "diag_fd_ptr/fd";
    diag_fd_ptr = (int *) dlsym(handle, "diag_fd");
    if (!diag_fd_ptr)
        diag_fd_ptr = (int *) dlsym(handle, "fd");
    if (!diag_fd_ptr)
        goto fail;
    logging_mode = (int *) dlsym(handle, "logging_mode");

    /*
     * It seems that calling Diag_LSM_Init here is not necessary.
     *
     * When diag_fd_ptr is not set, Diag_LSM_Init will try to open
     * /dev/diag, which will fail since we've already opened one
     * (errno=EEXIST).
     *
     * When diag_fd_ptr is set, Diag_LSM_Init will also do nothing
     * related to our goal.
     */
    *diag_fd_ptr = diag_fd;
    (*diag_switch_logging)(mode, NULL);

    if (logging_mode && *logging_mode != mode) {
        LOGE("diag_switch_logging in libdiag.so failed\n");
        ret = -1;
    } else if (!logging_mode) {
        LOGW("Missing symbol logging_mode in libdiag.so, "
             "assume diag_switch_logging succeeded\n");
        ret = 0;
    } else {
        ret = 0;
    }

    // We have never created new threads in libdiag.so, so we can close it.
    dlclose(handle);
    return ret;
fail:
    LOGE("Missing symbol %s in libdiag.so\n", err);
    dlclose(handle);
    return -1;
}

static int
enable_logging (int diag_fd, int mode)
{
    int ret = -1;

    /*
     * EXPERIMENTAL (NEXUS 6 ONLY):
     * 1. check use_mdm
     * 2. Register a DCI client
     * 3. Send DCI control command
     */
    ret = ioctl(diag_fd, DIAG_IOCTL_REMOTE_DEV, &use_mdm);
    if (ret < 0) {
        printf("ioctl DIAG_IOCTL_REMOTE_DEV fails, with ret val = %d\n", ret);
        perror("ioctl DIAG_IOCTL_REMOTE_DEV");
    } else {
        // LOGD("DIAG_IOCTL_REMOTE_DEV use_mdm=%d\n", use_mdm);
    }

    // Register a DCI client
    struct diag_dci_reg_tbl_t dci_client;
    dci_client.client_id = 0;
    dci_client.notification_list = 0;
    dci_client.signal_type = SIGPIPE;
    // dci_client.token = use_mdm;
    dci_client.token = 0;
    ret = ioctl(diag_fd, DIAG_IOCTL_DCI_REG, &dci_client);
    if (ret < 0) {
        printf("ioctl DIAG_IOCTL_DCI_REG fails, with ret val = %d\n", ret);
        perror("ioctl DIAG_IOCTL_DCI_REG");
    } else {
        client_id = ret;
        // printf("DIAG_IOCTL_DCI_REG client_id=%d\n", client_id);
    }

    /*
     * EXPERIMENTAL (NEXUS 6 ONLY): configure the buffering mode to circular
     */
    struct diag_buffering_mode_t buffering_mode;
    // buffering_mode.peripheral = use_mdm;
    buffering_mode.peripheral = 0;
    buffering_mode.mode = DIAG_BUFFERING_MODE_STREAMING;
    buffering_mode.high_wm_val = DEFAULT_HIGH_WM_VAL;
    buffering_mode.low_wm_val = DEFAULT_LOW_WM_VAL;

    ret = ioctl(diag_fd, DIAG_IOCTL_PERIPHERAL_BUF_CONFIG, &buffering_mode);
    if (ret < 0) {
        printf("ioctl DIAG_IOCTL_PERIPHERAL_BUF_CONFIG fails, with ret val = %d\n", ret);
        //perror("ioctl DIAG_IOCTL_PERIPHERAL_BUF_CONFIG");
    }

    /*
     * Enable logging mode:
     *
     * DIAG_IOCTL_SWITCH_LOGGING has multiple versions. They require different arguments (which have
     * different fields and whose lengths are also different). However, it seems there is no way to
     * directly determine the version of DIAG_IOCTL_SWITCH_LOGGING. So some tricks can not be avoided
     * here.
     *
     * A traditional way is to try one by one. But it can cause undefined behaviour. Specially, when
     * a new verison of DIAG_IOCTL_SWITCH_LOGGING is introduced, it may not report an error. But some
     * new fields will be out of bounds. Consequently, it may cause random bugs, which is confusing.
     *
     * So a more elegant way is to explicitly probe the length of DIAG_IOCTL_SWITCH_LOGGING's argument.
     * And the version can be deduced from the length. It is not very precise, but it is enough at least
     * for now.
     */
    // Testing: get device info
    char *board_pf_cmd = "su -c getprop ro.board.platform";
    char board_name[256];
    FILE *fp;
    if ((fp = popen(board_pf_cmd, "r")) != NULL) {
        while (fgets(board_name, 256, fp) != NULL) {
            // printf("OUTPUT: %s\n", board_name);
        }
        pclose(fp);
    }

    char *sys_ver_cmd = "su -c getprop ro.build.version.release";
    char system_version[256];
    if ((fp = popen(sys_ver_cmd, "r")) != NULL) {
        while (fgets(system_version, 256, fp) != NULL) {
            // printf("OUTPUT: %s\n", system_version);
        }
        pclose(fp);
    }

    long arglen = probe_ioctl_arglen(DIAG_IOCTL_SWITCH_LOGGING, sizeof(struct diag_logging_mode_param_t_q));

    // IAN: fixed bug that checked for system_version and added support for Android 14. This change is in my FORKED repo
    if (strstr(board_name, "lito") != NULL && strstr(system_version, "11") != NULL || strstr(system_version, "14") != NULL){
        // printf("MATCHED.\n");
        /* Android 11.0.0 (RD1A.201105.003.C1)
         * Reference:
         *   https://android.googlesource.com/kernel/msm.git/+/refs/tags/android-11.0.0_r0.27/drivers/char/diag/diagchar_core.c
         */
        struct diag_logging_mode_param_t_q new_mode;
        struct diag_con_all_param_t con_all;
            con_all.diag_con_all = 0xff;
        ret = ioctl(diag_fd, DIAG_IOCTL_QUERY_CON_ALL, &con_all);
        if (ret == 0)
            new_mode.peripheral_mask = con_all.diag_con_all;
        else
            new_mode.peripheral_mask = 0x7f;
        new_mode.req_mode = mode;
        new_mode.pd_mask = 0;
        new_mode.mode_param = 1;
        new_mode.diag_id = 0;
        new_mode.pd_val = 0;
        new_mode.peripheral = 0;
        new_mode.device_mask = 1 << DIAG_MD_LOCAL;
        ret = ioctl(diag_fd, DIAG_IOCTL_SWITCH_LOGGING, &new_mode);
        // printf("Enable for Android 11: %d\n", ret);
        goto next;
    }
    // Testing end
    // LOGD("Not pixel-5 or Android 11: arglen=%ld, struct_q_size=%lu\n", arglen, sizeof(struct diag_logging_mode_param_t_q));
    switch (arglen) {
        
        case sizeof(struct diag_logging_mode_param_t_pie): {
            /* Android 9.0 mode
             * Reference: https://android.googlesource.com/kernel/msm.git/+/android-9.0.0_r0.31/drivers/char/diag/diagchar_core.c
             */
            struct diag_logging_mode_param_t_pie new_mode;
            new_mode.req_mode = mode;
            new_mode.mode_param = 0;
            new_mode.pd_mask = 0;
            new_mode.peripheral_mask = DIAG_CON_ALL;
            ret = ioctl(diag_fd, DIAG_IOCTL_SWITCH_LOGGING, &new_mode);
            
            if(ret >= 0)
                break;
        }
        case sizeof(struct diag_logging_mode_param_t): {
            /* Android 7.0 mode
             * Reference: https://android.googlesource.com/kernel/msm.git/+/android-7.1.0_r0.3/drivers/char/diag/diagchar_core.c
             */
            struct diag_logging_mode_param_t new_mode;
            new_mode.req_mode = mode;
            new_mode.peripheral_mask = DIAG_CON_ALL;
            new_mode.mode_param = 0;
            ret = ioctl(diag_fd, DIAG_IOCTL_SWITCH_LOGGING, &new_mode);
            
            if(ret >= 0)
              break;
        }
        case sizeof(int):
            /* Android 6.0 mode
             * Reference: https://android.googlesource.com/kernel/msm.git/+/android-6.0.0_r0.9/drivers/char/diag/diagchar_core.c
             */
            ret = ioctl(diag_fd, DIAG_IOCTL_SWITCH_LOGGING, &mode);
            if (ret >= 0)
                break;
            /*
             * Is it really necessary? It seems that the kernel will simply ignore all the fourth and subsequent
             * arguments of ioctl. But similar lines do exist in libdiag.so. Why?
             * Reference: https://android.googlesource.com/kernel/msm.git/+/android-10.0.0_r0.87/fs/ioctl.c#692
             */
            ret = ioctl(diag_fd, DIAG_IOCTL_SWITCH_LOGGING, &mode, 12, 0, 0, 0, 0);
            if (ret >= 0)
                break;
        case 0:
            // Yuanjie: the following works for Samsung S5
            ret = ioctl(diag_fd, DIAG_IOCTL_SWITCH_LOGGING, (long) mode);
            if (ret >= 0)
                break;
            // Same question as above: Is it really necessary?
            // Yuanjie: the following is used for Xiaomi RedMi 4
            ret = ioctl(diag_fd, DIAG_IOCTL_SWITCH_LOGGING, (long) mode, 12, 0, 0, 0, 0);
            if (ret >= 0)
                break;
        default:
            LOGW("ioctl DIAG_IOCTL_SWITCH_LOGGING with arglen=%ld is not supported\n", arglen);
            ret = -8080;
            break;
    }
next:
    if (ret < 0 && ret != -8080)
        LOGE("ioctl DIAG_IOCTL_SWITCH_LOGGING with arglen=%ld is supported, "
             "but it failed (%s)\n", arglen, strerror(errno));
    // else if (ret >= 0)
    //    LOGI("ioctl DIAG_IOCTL_SWITCH_LOGGING with arglen=%ld succeeded\n", arglen);
    //    printf("ioctl DIAG_IOCTL_SWITCH_LOGGING with arglen=%ld succeeded\n", arglen);

    if (ret < 0) {
        /* Ultimate approach: Use libdiag.so */
        ret = __enable_logging_libdiag(mode);
        // if (ret >= 0)
        //     LOGI("Using libdiag.so to switch logging succeeded\n");
    }
    if (ret >= 0) {
        // LOGD("Enable logging mode success.\n");

        // Register a DCI client
        struct diag_dci_reg_tbl_t dci_client;
        dci_client.client_id = 0;
        dci_client.notification_list = 0;
        dci_client.signal_type = SIGPIPE;
        // dci_client.token = use_mdm;
        dci_client.token = 0;
        ret = ioctl(diag_fd, DIAG_IOCTL_DCI_REG, &dci_client);
        if (ret < 0) {
            // LOGD("ioctl DIAG_IOCTL_DCI_REG fails, with ret val = %d\n", ret);
            // perror("ioctl DIAG_IOCTL_DCI_REG");
        } else {
            client_id = ret;
            // LOGD("DIAG_IOCTL_DCI_REG client_id=%d\n", client_id);
        }

        /*
         * Configure the buffering mode to circular
         */
        struct diag_buffering_mode_t buffering_mode;
        // buffering_mode.peripheral = use_mdm;
        buffering_mode.peripheral = 0;
        buffering_mode.mode = DIAG_BUFFERING_MODE_STREAMING;
        buffering_mode.high_wm_val = DEFAULT_HIGH_WM_VAL;
        buffering_mode.low_wm_val = DEFAULT_LOW_WM_VAL;

        ret = ioctl(diag_fd, DIAG_IOCTL_PERIPHERAL_BUF_CONFIG, &buffering_mode);
        if (ret < 0) {
            // LOGD("ioctl DIAG_IOCTL_PERIPHERAL_BUF_CONFIG fails, with ret val = %d\n", ret);
            // perror("ioctl DIAG_IOCTL_PERIPHERAL_BUF_CONFIG");
        }

    } else {
        error("ioctl");
        // LOGD("Failed to enable logging mode: %s.\n", strerror(errno));
    }

    return ret;
}

int main(void)
{
    /* Set the standard output to unbuffered */
    
    setvbuf(stdout, NULL, _IONBF, 0);
    
    char* diag_buffer = malloc(BUFFER_LEN);
    
    int return_value;
    
    /* Connect to Diag */
    
    diag_fd = open("/dev/diag", O_RDWR | O_LARGEFILE);
    
    if (diag_fd < 0) error("open");

    /* Enable logging mode */

    enable_logging(diag_fd, mode);

    /* Build header for Diag requests */
    
    *(unsigned int*) diag_buffer = USER_SPACE_DATA_TYPE;
    
    if(use_mdm) {
        *((int*)(diag_buffer + 4)) = 0xffffffff;
    }

    /* Initialize TCP server */
    
    int server = socket(AF_INET, SOCK_STREAM, 0);
    if (server < 0) error("socket");

    struct sockaddr_in server_info = {
        .sin_family = AF_INET,
        .sin_port = htons(QCSUPER_TCP_PORT),
        .sin_addr = {
            .s_addr = htonl(INADDR_ANY)
        }
    };

    const int DO_REUSE_ADDR = 1;
    return_value = setsockopt(server, SOL_SOCKET, SO_REUSEADDR, &DO_REUSE_ADDR, sizeof DO_REUSE_ADDR);
    if (return_value < 0) error("setsockopt");
    
    return_value = bind(server, (struct sockaddr *) &server_info, sizeof(server_info));
    if (return_value < 0) error("bind");
    
    return_value = listen(server, 16);
    if (return_value < 0) error("listen");
    
    printf("Connection to Diag established\n");
    
    /* Accept TCP connections, and read from diag and clients, using poll() */
    
    fds[0].fd = server;
    fds[0].events = POLLIN;
    number_fds = 1;
    
    pthread_t diag_thread;
    real_pthread_create = dlsym(RTLD_NEXT, "pthread_create");
    real_pthread_create(&diag_thread, NULL, &diag_read_thread, NULL);

    while(1) {
        return_value = poll(fds, number_fds, -1);
        if (return_value < 0) error("poll");
        
        for(int i = 0; i < number_fds; i++) {
            struct pollfd some_fd = fds[i];
            
            if(!(some_fd.revents & POLLIN)) {
                continue;
            }
            
            if(some_fd.fd == server) {
                struct sockaddr_in client_info = { 0 };
                
                socklen_t client_info_size = sizeof(client_info);
                int client = accept(server, (struct sockaddr *) &client_info, &client_info_size);
                
                if (client < 0) error("read");
                
                if(number_fds > FDS_LEN) {
                    fprintf(stderr, "Error: too much clients\n");
                    exit(1);
                }
        
                pthread_mutex_lock(&fdset_mutex);
        
                fds[number_fds].fd = client;
                fds[number_fds].events = POLLIN;
                number_fds++;
        
                pthread_mutex_unlock(&fdset_mutex);
            }
            else {
                int bytes_read = read(some_fd.fd, diag_buffer + (use_mdm ? 8 : 4), BUFFER_LEN - (use_mdm ? 8 : 4));
                if(bytes_read < 1) {
                    goto remove_fd;
                }
                
                return_value = write(diag_fd, diag_buffer, bytes_read + (use_mdm ? 8 : 4));
                if (return_value < 0) {
                    if(errno != EFAULT) {
                        error("write");
                    }
                    else {
                        #ifdef DEBUG
                            printf("Note: EFAULT was encountered while writing message\n");
                        #endif
                        
                        // EFAULT was received, simulate a DIAG_BAD_CMD_F
                        
                        char bad_cmd[] = { 0x13, 0x62, 0xd2, 0x7e };
        
                        pthread_mutex_lock(&fdset_mutex);
                        
                        for(int j = 1; j < number_fds; j++) {
                            write(fds[j].fd, bad_cmd, sizeof(bad_cmd));
                        }
        
                        pthread_mutex_unlock(&fdset_mutex);
                    }
                }
                
                #ifdef DEBUG
                    printf("Debug: transmitting message of size %d\n", bytes_read + (use_mdm ? 8 : 4));
                #endif
                
                continue;

remove_fd:
                pthread_mutex_lock(&fdset_mutex);
                
                memcpy(&fds[i], &fds[i + 1], sizeof(fds[0]) * (FDS_LEN - number_fds));
                number_fds--;
        
                pthread_mutex_unlock(&fdset_mutex);
            }
        }
    }
}
