from celery import Celery
import ezkl
import tempfile

SRS_PATH = '15.srs'
MODEL_PATH = 'model.onnx'
PK_PATH = 'pk.key'


app = Celery('tasks', backend='redis://localhost', broker='pyamqp://guest@localhost//')

@app.task
def add(x, y):
    return x + y

@app.task
def gen_srs():
    return ezkl.gen_srs(logrows=15, srs_path='15.srs')

@app.task
def compute_proof():
    with tempfile.NamedTemporaryFile() as pffo:
        ezkl.prove('input.json','network.onnx','pk.key',
                   pffo.name,
                   '15.srs','evm','single','settings.json',False)
        return pffo.read()
    
