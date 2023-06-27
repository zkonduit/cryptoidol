from flask import Flask, request
from flask import render_template, request
from werkzeug.utils import secure_filename
from tasks import compute_proof

app = Flask(__name__)

@app.route("/")
def hello_world():
    return "<p>Hello, World!</p>"



@app.route('/upload')
def upload_form_file():
   return render_template('upload.html')
	
@app.route('/uploader', methods = ['GET', 'POST'])
def upload_file():
   if request.method == 'POST':
      f = request.files['file']
      # todo: give this a permanent name and kick off the fft and compute_proof async tasks
      # return the task identifier 
      f.save('./tempname') 
      return 'file uploaded successfully'
