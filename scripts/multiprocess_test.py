import multiprocessing

def test_process():
    print(f"Running in process: {multiprocessing.current_process().name}")

if __name__ == "__main__":
    multiprocessing.set_start_method("spawn", force=True)
    p = multiprocessing.Process(target=test_process)
    p.start()
    p.join()