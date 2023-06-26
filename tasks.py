from celery import Celery
import ezkl

app = Celery('tasks', backend='redis://localhost', broker='pyamqp://guest@localhost//')

@app.task
def add(x, y):
    return x + y

@app.task
def gen_srs():
    return ezkl.gen_srs(logrows=15, srs_path='15.srs')
