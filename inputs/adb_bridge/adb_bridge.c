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
 */

#define QCSUPER_TCP_PORT 43555

#define BUFFER_LEN 1024 * 1024 * 10
#define FDS_LEN 4096

#define USER_SPACE_DATA_TYPE 0x00000020

#define QCSUPER_SIZE_FIELD_SIZE 4
#define DIAG_DATATYPE_FIELD_SIZE 4

#define DIAG_CON_APSS 1 /* Bit mask for APSS */
#define DIAG_CON_MPSS 2 /* Bit mask for MPSS */
#define DIAG_CON_LPASS 4 /* Bit mask for LPASS */
#define DIAG_CON_WCNSS 8 /* Bit mask for WCNSS */
#define DIAG_CON_SENSORS 16 /* Bit mask for Sensors */

#define DIAG_CON_ALL (DIAG_CON_APSS | DIAG_CON_MPSS | DIAG_CON_LPASS | DIAG_CON_WCNSS | DIAG_CON_SENSORS)

// make && adb push hello /data/local/tmp && adb forward tcp:43555 tcp:43555 && adb shell "su -c /data/local/tmp/hello"

struct pollfd fds[FDS_LEN] = { 0 };
int number_fds = 0;
int diag_fd;

int use_mdm = 0;

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

int main(void) {
    char* diag_buffer = malloc(BUFFER_LEN);
    
    int return_value;
    
    /* Connect to Diag */
    
    diag_fd = open("/dev/diag", O_RDWR);
    
    if (diag_fd < 0) error("open");

    const unsigned long DIAG_IOCTL_SWITCH_LOGGING = 7;
    const unsigned long DIAG_IOCTL_REMOTE_DEV = 32;
    const int MEMORY_DEVICE_MODE = 2;
    
    // The following logic was mostly based on this
    // algorithm:
    // https://github.com/mobile-insight/mobileinsight-mobile/blob/master/diag_revealer/qcom/jni/diag_revealer.c#L693
    
    const int mode_param[] = { MEMORY_DEVICE_MODE, DIAG_CON_ALL, 0 }; // diag_logging_mode_param_t
    const int mode_param_android9[] = { MEMORY_DEVICE_MODE, DIAG_CON_ALL, 0, 0 }; // diag_logging_mode_param_t_pie
    
    if(ioctl(diag_fd, DIAG_IOCTL_REMOTE_DEV, &use_mdm) < 0) {
        error("ioctl");
    }

    if(ioctl(diag_fd, DIAG_IOCTL_SWITCH_LOGGING, MEMORY_DEVICE_MODE, 0, 0, 0) < 0 &&
       ioctl(diag_fd, DIAG_IOCTL_SWITCH_LOGGING, &mode_param, sizeof(mode_param), 0, 0, 0, 0) < 0 && // Android 7.0
       ioctl(diag_fd, DIAG_IOCTL_SWITCH_LOGGING, &mode_param_android9, sizeof(mode_param_android9), 0, 0, 0, 0) < 0 && // Android 9.0
       ioctl(diag_fd, DIAG_IOCTL_SWITCH_LOGGING, &MEMORY_DEVICE_MODE, 0, 0, 0) < 0 &&
       ioctl(diag_fd, DIAG_IOCTL_SWITCH_LOGGING, MEMORY_DEVICE_MODE, 12, 0, 0, 0, 0) < 0 && // Redmi 4
       ioctl(diag_fd, DIAG_IOCTL_SWITCH_LOGGING, &MEMORY_DEVICE_MODE, 12, 0, 0, 0, 0) < 0) {
        error("ioctl");
    }
    
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
    pthread_create(&diag_thread, NULL, &diag_read_thread, NULL);

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
