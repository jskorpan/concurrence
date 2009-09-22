import stackless

def task1():
    for i in range(100):
        print '1', i

def task2():
    for i in range(100):
        print '2', i

if __name__ == '__main__'
    stackless.tasklet(task1)()
    stackless.tasklet(task1)()
    while stackless.getruncount() > 1:
        stackless.schedule()

