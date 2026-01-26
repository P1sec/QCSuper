import os

def read_from_pipe(pipe_path='/tmp/tshark_pipe'):
    if not os.path.exists(pipe_path):
        print(f"Error: The named pipe {pipe_path} does not exist. Make sure that TsharkLive has created it.")
        return

    try:
        with open(pipe_path, 'r') as pipe:
            for line in pipe:
                print(f"{line.strip()}")
    except KeyboardInterrupt:
        print("\n")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    read_from_pipe()
