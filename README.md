# cryptoidol


##Server
The server will use flask and celery. 


Install
```
conda create --name idol
conda activate idol
pip install celery
pip install redis
pip install ezkl
```

Spin up rabbitmq for the task queue broker and redis for the results.
```
docker run -d -p 5672:5672 rabbitmq
docker run -d -p 6379:6379 redis
```

Start the celery

```
celery -A tasks worker --loglevel=INFO
```