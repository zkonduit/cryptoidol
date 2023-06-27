# cryptoidol


##Server
The server will use flask and celery. 


Install
```
conda create --name idol
conda activate idol
pip install celery
pip install redis
pip install flask
pip install ezkl
```

Spin up rabbitmq for the task queue broker and redis for the results.
```
docker run -d -p 5672:5672 rabbitmq
docker run -d -p 6379:6379 redis
```

Start celery
```
celery -A tasks worker --loglevel=INFO
```

Get a proof from a worker
```python
import tasks
inp = open('input.json').read() # put the json in a string
result = tasks.compute_proof.delay(inp) 
result.ready() # returns true when ready
result.get() # bytes of proof
```

Run the flask server
```
flask run
```
`127.0.0.1:5000/upload` to upload a file

