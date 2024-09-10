import json
import tempfile
import librosa
import numpy as np
from flask import request, jsonify, Flask
import os
from flask_cors import CORS
from pydub import AudioSegment
from mclbn256 import Fr
import api_key
import requests
import time
import logging
import traceback

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


app = Flask(__name__)
app.config["TEMPLATES_AUTO_RELOAD"] = True
CORS(app)


# mfcc extraction from augmented data


#extraction mel spectrogram
def extract_mel_spec(filename):
    x,sr=librosa.load(filename,duration=3,offset=0.5)

    # trim silence
    xt, _ = librosa.effects.trim(x, top_db=60, frame_length=1024, hop_length=128)

    # convert trimmed audio to melspectrogram
    X = librosa.feature.melspectrogram(y=xt, sr=sr)
    Xdb = librosa.power_to_db(X, ref=np.max)
    Xdb = Xdb.reshape(1,128,-1)

    return Xdb


def extract_bytes_addr(addr): 
    addr_int = int(addr, 0)
    rep = Fr(addr_int)

    ser = rep.serialize()

    first_byte = int.from_bytes(ser[0:8], "little")
    second_byte = int.from_bytes(ser[8:16], "little")
    third_byte = int.from_bytes(ser[16:24], "little")
    fourth_byte = int.from_bytes(ser[24:32], "little")

    return [first_byte, second_byte, third_byte, fourth_byte]


def u64_to_fr(array):
    reconstructed_bytes = array[0].to_bytes(8, byteorder='little') \
                            + array[1].to_bytes(8, byteorder='little') \
                              + array[2].to_bytes(8, byteorder='little') \
                                + array[3].to_bytes(8, byteorder='little')
    return Fr(reconstructed_bytes)


@app.route('/prove/', methods=["POST"])
def prove_task():
    try:
        audio_file = request.files['audio'].read()

        with tempfile.NamedTemporaryFile(mode="wb+") as input_json_buffer:
            with tempfile.NamedTemporaryFile(mode="wb+") as audio_input_buffer:
                audio_input_buffer.write(audio_file)
                audio_input_buffer.flush()

                val = extract_mel_spec(audio_input_buffer.name)

                # 0 pad 2nd dim to max size
                if val.shape[2] < 130:
                    val = np.pad(
                        val, ((0, 0), (0, 0), (0, 130-val.shape[2])))
                # truncate to max size
                else:
                    val = val[:, :, :130]

                # setup input.json
                inp = {
                    "input_data": [val.flatten().tolist()],
                }
                inp_json_str = json.dumps(inp)
                input_json_buffer.write(inp_json_str.encode('utf-8'))

                # seek buffer to 0 before sending
                input_json_buffer.seek(0)

                print("updating artifacts with new input.json")

                res = requests.put(
                    url=f"{api_key.ARCHON_URL}/artifact/idol-3?deployment=prod-1",
                    headers={"X-API-KEY": api_key.API_KEY},
                    files={
                        "data": input_json_buffer
                    }
                )

                res.raise_for_status()
                data = json.loads(res.content.decode('utf-8'))
                latest_uuid = data["latest_uuid"]
                print("latest_uuid: ", latest_uuid)

                # gen-witness and prove
                try:
                    res = requests.post(
                        url=f"{api_key.ARCHON_URL}/recipe?callback_url={api_key.CALLBACK_URL}",
                        headers={
                            "X-API-KEY": api_key.API_KEY,
                            "Content-Type": "application/json",
                        },
                        json=[  # Note: This is now a list, not a dict
                            {
                                "command": [
                                    "gen-witness",
                                    f"--data input_{latest_uuid}.json",
                                    f"--compiled-circuit model.compiled",
                                    f"--output witness_{latest_uuid}.json"
                                ],
                                "artifact": "idol-3",
                                "deployment": "prod-1",
                                "binary": "ezkl"
                            },
                            {
                                "command": [
                                    "prove",
                                    f"--witness witness_{latest_uuid}.json",
                                    f"--compiled-circuit model.compiled" ,
                                    "--pk-path pk.key",
                                    f"--proof-path proof_{latest_uuid}.json",
                                ],
                                "artifact": "idol-3",
                                "deployment": "prod-1",
                                "binary": "ezkl",
                                "output_path": [f"proof_{latest_uuid}.json"]
                            },
                        ]
                    )

                    if res.status_code >= 400:
                        print(f"Error: HTTP {res.status_code}")
                        error_message = res.json().get('message', 'No error message provided')
                        print(f"Error message: {error_message}")
                    else:
                        print("Request successful")
                        print(res.json())

                except Exception as e:
                    print(f"Error parsing JSON response: {str(e)}")

                res.raise_for_status()
                data = json.loads(res.content.decode('utf-8'))
                print("full data: ", data)
                print("id: ", str(data["id"]))

                return jsonify({
                    "status": "ok",
                    "id": str(data["id"])
                })

    except EOFError as e:
        logger.exception("EOFError occurred during audio file processing")
        logger.error(f"Error message: {str(e)}")
        logger.error(f"Error traceback: {traceback.format_exc()}")
        return "Incomplete file sent, you may want to try resubmitting again.", 500

    except Exception as e:
        logger.exception("An error occurred during prove task")
        logger.error(f"Error message: {str(e)}")
        logger.error(f"Error traceback: {traceback.format_exc()}")
        return repr(e), 500


@app.route('/callback/', methods=["POST"])
def callback():
    try:
        data = request.data
        data_output = json.loads(data)
        print(data_output)

        if data_output[1]["status"] == "Errored":
            with open(os.path.join("proof_data", str(data_output[0]['recipe_id'])) + ".json", "w") as f:
                to_save = {
                    "status": "error",
                    "error": data_output[1]["logs"]
                }
                json.dump(to_save, f)

        if 'prove' in data_output[1]['command']['command']:
            # Extract the proof_path
            proof_path = next(arg for arg in data_output[1]['command']['command'] if arg.startswith('--proof-path'))
            proof_file = proof_path.split('--proof-path ')[1]
            print(f"proof file in callback: {proof_file}")

        else:
            print("No proof file found in the data.")

            with open(os.path.join("proof_data", str(data_output[0]['recipe_id'])) + ".json", "w") as f:
                to_save = {
                    "status": "error",
                    "error": "No proof file found"
                }
                json.dump(to_save, f)

            return jsonify({"status": "error", "message": "No proof file found in response"}), 400


        res = requests.get(
            url=f"{api_key.ARCHON_URL}/artifact/idol-3/file/{proof_file}?deployment=prod-1",
            headers={ "X-API-KEY": api_key.API_KEY},
        )

        proof_data = res.json()

        to_save = {
            "status": "success",
            "score_hex": proof_data["pretty_public_inputs"]["outputs"][0][0],
            "score": proof_data["pretty_public_inputs"]["rescaled_outputs"][0][0],
            "proof": proof_data["hex_proof"]
        }

        with open(os.path.join("proof_data", str(data_output[0]['recipe_id'])) + ".json", "w") as f:
            json.dump(to_save, f)

        return jsonify({
            "status": "ok"
        })

    except Exception as e:
        with open(os.path.join("proof_data", str(data_output[0]['recipe_id'])) + ".json", "w") as f:
            to_save = {
                "status": "error"
            }
            json.dump(to_save, f)

        print(repr(e))

        return repr(e), 500


@app.route('/recipe/<id>/')
def recipe(id):
    saved_file = os.path.join("proof_data", str(id) + ".json")
    if not os.path.exists(saved_file):
        return "Not Found", 400

    else:
        with open(saved_file, "r") as f:
            f = json.load(f)

        return jsonify(f)


@app.route('/', methods=['GET'])
def index():
    return jsonify({'status': 'ok', 'res': "CryptoIdol Pre-processing Server"})


if __name__ == '__main__':
    with open(os.path.join("test_files", "angry.wav"), "rb") as audio_file:
        with tempfile.NamedTemporaryFile(mode="wb+") as input_json_buffer:
            val = extract_mel_spec(audio_file)

            # 0 pad 2nd dim to max size
            if val.shape[2] < 130:
                val = np.pad(
                    val, ((0, 0), (0, 0), (0, 130-val.shape[2])))
            # truncate to max size
            else:
                val = val[:, :, :130]

            # setup input.json
            inp = {
                "input_data": [val.flatten().tolist()],
            }
            inp_json_str = json.dumps(inp)
            input_json_buffer.write(inp_json_str.encode('utf-8'))

            # seek buffer to 0 before sending
            input_json_buffer.seek(0)

            print("updating artifacts with new input.json")

            headers = {
                'X-API-KEY': api_key.API_KEY,
                "Content-Type": "multipart/form-data"
            }
            inp_json_str = json.dumps(inp)
            input_json_buffer.write(inp_json_str.encode('utf-8'))

            # seek buffer to 0 before sending
            input_json_buffer.seek(0)

            headers = {
                'X-API-KEY': api_key.API_KEY,
                "Content-Type": "multipart/form-data"
            }

            res = requests.put(
                url=f"{api_key.ARCHON_URL}/artifact/idol-3?deployment=prod-1",
                headers={"X-API-KEY": api_key.API_KEY},
                files={
                    "data": input_json_buffer,
                }
            )

            res.raise_for_status()
            data = json.loads(res.content.decode('utf-8'))
            print(data)
            latest_uuid = data["latest_uuid"]
            print("latest_uuid: ", latest_uuid)

            # gen-witness and prove
            try:
                res = requests.post(
                    url=f"{api_key.ARCHON_URL}/recipe",
                    headers={
                        "X-API-KEY": api_key.API_KEY,
                        "Content-Type": "application/json",
                    },
                    json=[  # Note: This is now a list, not a dict
                        {
                            "command": [
                                "gen-witness",
                                f"--data input_{latest_uuid}.json",
                                f"--compiled-circuit model.compiled",
                                f"--output witness_{latest_uuid}.json"
                            ],
                            "artifact": "idol-3",
                            "deployment": "prod-1",
                            "binary": "ezkl"
                        },
                        {
                            "command": [
                                "prove",
                                f"--witness witness_{latest_uuid}.json",
                                f"--compiled-circuit model.compiled",
                                "--pk-path pk.key",
                                f"--proof-path proof_{latest_uuid}.json"
                            ],
                            "artifact": "idol-3",
                            "deployment": "prod-1",
                            "binary": "ezkl"
                        },
                    ]
                )

                if res.status_code >= 400:
                    print(f"Error: HTTP {res.status_code}")
                    error_message = res.json().get('message', 'No error message provided')
                    print(f"Error message: {error_message}")
                else:
                    print("Request successful")
                    print(res.json())

            except Exception as e:
                print(f"Error parsing JSON response: {str(e)}")

            data = json.loads(res.content.decode('utf-8'))
            print("full data: ", data)
            print("id: ", data["id"])

            cluster_id = data["id"]


            query_count = 0
            proof_data = None

            while query_count < 60:
                time.sleep(20)
                # get job status
                # pass id to client so client polls
                res = requests.get(
                    url=f"{api_key.ARCHON_URL}/recipe/{str(cluster_id)}",
                    headers={
                        "X-API-KEY": api_key.API_KEY,
                    }
                )
                res.raise_for_status()
                data = json.loads(res.content.decode('utf-8'))
                print("witness data: ", data[0])
                print("prove data: ", data[1])
                # print(data)
                print("prove status: ", data[1]['status'])

                status = data[1]['status']

                if status == "Complete":
                    print("COMPLETE")
                    print(data)

                    res = requests.get(
                        url=f"{api_key.ARCHON_URL}/artifact/idol-3/file/proof_{latest_uuid}.json?deployment=prod-1",
                        headers={ "X-API-KEY": api_key.API_KEY},
                    )

                    res.raise_for_status()

                    proof_data = res.json()

                    print("hex_proof: ", proof_data["hex_proof"])
                    print("instances: ", proof_data["pretty_public_inputs"]["outputs"])

                    break

                if status == "Errored":
                    print("ERRORED")
                    print(data)
                    break


                query_count += 1
