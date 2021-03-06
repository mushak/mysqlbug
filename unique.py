#!/usr/bin/python

import time
import random
import multiprocessing
import Queue
import MySQLdb
import optparse


class DatabaseWorker (multiprocessing.Process):

    def __init__(self, queue):
        self.queue = queue
        super(DatabaseWorker, self).__init__()

    def run(self):
        self.db = MySQLdb.connect(host='localhost', db='test', user='root', passwd='', unix_socket='/var/lib/mysql/mysql.sock')
        self.db.autocommit(True)
        cursor = self.db.cursor()
        cursor.execute('set transaction isolation level read committed')
        cursor.close()
        self.task()
        self.db.close()

    def task(self):
        pass


class DeleteWorker (DatabaseWorker):

    def task(self):
        delay_queue = Queue.Queue()

        q1 = multiprocessing.JoinableQueue()
        q2 = multiprocessing.JoinableQueue()

        w1 = InsertWorker(q1)
        w1.start()

        w2 = InsertWorker(q2)
        w2.start()
        
        while True:
            delete_id = self.queue.get()
            if delete_id == 0:
                while not delay_queue.empty():
                    insert_id = delay_queue.get()
                    q1.put(insert_id)
                    q2.put(insert_id)
                    q2.join()
                    q1.join()
                self.queue.task_done()
                break
            delay_queue.put(delete_id)

            try:
                cursor = self.db.cursor()
                cursor.execute('delete from test where v1 = %d' % (delete_id))
                cursor.close()
            except:
                pass


            if delay_queue.qsize() > 100:
                while not delay_queue.empty():
                    insert_id = delay_queue.get()
                    q1.put(insert_id)
                    q2.put(insert_id)
                    q2.join()
                    q1.join()

            self.queue.task_done()

        q1.put(0)
        w1.join()
        q2.put(0)
        w2.join()


class InsertWorker (DatabaseWorker):

    def __init__(self, queue, joinable=True):
        self.joinable = joinable
        super(InsertWorker, self).__init__(queue)

    def task(self):
        while True:
            id = self.queue.get()
            if id == 0:
                if self.joinable:
                    self.queue.task_done()
                break
            try:
                cursor = self.db.cursor()
                cursor.execute('insert into test (v1, v2) values (%d, %d)' % (id, random.randint(1, 10000000)));
                cursor.close()
            except:
                pass
            if self.joinable:
                self.queue.task_done()


def cleanup():
    db = MySQLdb.connect(host='localhost', db='test', user='root', passwd='', unix_socket='/var/lib/mysql/mysql.sock')
    db.autocommit(True)
    cursor = db.cursor()
    cursor.execute('drop table if exists test')
    cursor.close()
    db.close()

def prepare(size=0, threads=1):
    if not size > 0:
        return

    db = MySQLdb.connect(host='localhost', db='test', user='root', passwd='', unix_socket='/var/lib/mysql/mysql.sock')
    db.autocommit(True)
    cursor = db.cursor()
    cursor.execute('create table `test` (`id` int(11) not null auto_increment, `v1` int(11) not null, `v2` int(11) not null default 1, `v3` int(11) not null default 2, primary key (`id`), unique key `v1` (`v1`), key `v2` (`v2`) ) engine=innodb')
    cursor.close()
    db.close()

    q = [None] * threads
    w = [None] * threads
    
    for n in xrange(threads):
        q[n] = multiprocessing.Queue(16)
        w[n] = InsertWorker(queue=q[n], joinable=False)
        w[n].start()

    for i in xrange(1, size):
        n = i % threads
        q[n].put(i)

    for n in xrange(threads):
        q[n].put(0)

    w.join()

def run(size=0):
    if not size > 0:
        return

    random.seed()

    q = multiprocessing.JoinableQueue(16)
    w = DeleteWorker(q)
    w.start()

    while True:
        i = random.randint(1, size)
        q.put(i)
        q.join()

    q.put(0)
    w.join()

def main():
    parser = optparse.OptionParser()

    parser.add_option('-c', '--cleanup',
                      action='store_true', default=False, dest='cleanup')
    parser.add_option('-p', '--prepare',
                      action='store_true', default=False, dest='prepare')
    parser.add_option('-r', '--run',
                      action='store_true', default=False, dest='run')
    parser.add_option('-s', '--size',
                      action='store', type='int', default=0, dest='size')
    parser.add_option('-t', '--prepare-threads',
                      action='store', type='int', default=1, dest='prepare_threads')

    (options, args) = parser.parse_args()

    if int(options.cleanup) + int(options.prepare) + int(options.run) != 1:
        print 'Please specify one of --cleanup, --prepare or --run.'
        exit(1)

    if not options.cleanup and not options.size > 0:
        print 'Pleasae specify table size.'
        exit(1)

    if options.cleanup:
        cleanup()
    if options.prepare:
        prepare(size=options.size, threads=options.prepare_threads)
    if options.run:
        run(options.size)

if __name__ == '__main__':
    main()
