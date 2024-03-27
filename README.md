# CryptoIdol Preprocessing Server

This server helps to preprocess audio data before passing the data over to a proof generation cluster.


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

2. Run `poetry env use 3.9`

3. Run `poetry shell`, the previous command should initiate a virtual environment shell for you. Otherwise, run this line.

4. Run `poetry install`

5. Rename `api_key.py.example` to `api_key.py` and get the relevant variables.

6. Run `python app.py` to run a test upload.

7. Run `flask run` to start the development server.




