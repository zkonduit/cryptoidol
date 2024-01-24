# cryptoidol


## Docker

The server uses flask and celery. 

```
docker-compose up
```

Test getting proof from a worker
```python
curl -F audio=@test_files/angry.wav localhost:5000/prove 
```

## Development

1. [Install poetry.](https://python-poetry.org/docs/#installation)

2. Run `poetry shell`

3. Run `poetry install`

4. Rename `api_key.py.example` to `api_key.py` and get the relevant variables.

4. Run `python app.py` to run a test upload.

5. Run `flask run` to start the development server.




