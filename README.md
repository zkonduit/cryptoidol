# cryptoidol


##Server
The server uses flask and celery. 

```
docker-compose up
```

Test getting proof from a worker
```python
curl -F audio=@test_files/angry.wav localhost:5000/prove 
```


