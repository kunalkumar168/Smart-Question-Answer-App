from flask import Flask, request, render_template, session, redirect, url_for
import base64
import os
import vertexai
from vertexai.generative_models import GenerativeModel, Part
import vertexai.preview.generative_models as generative_models
from google.cloud import storage

# Create a Flask app

app = Flask(__name__)

# Set a secret key for the session
app.secret_key = os.urandom(24)

# Bucket Information
client = storage.Client()

# Initialize Vertex AI
vertexai.init(project="fair-gradient-419306", location="us-west1")

# Load Generative Model
#model = GenerativeModel("gemini-1.0-pro-vision-001")
#model = GenerativeModel("gemini-1.5-pro-preview-0409")

class MyApp():
    def __init__(self):
        self.model = GenerativeModel("gemini-1.5-pro-preview-0409")
        self.generation_config = {
                "max_output_tokens": 8192, # 2048 # 8192
                "temperature": 0.9,
                "top_p": 1,
            }
        self.safety_settings = {
                generative_models.HarmCategory.HARM_CATEGORY_HATE_SPEECH: generative_models.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                generative_models.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: generative_models.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                generative_models.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: generative_models.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                generative_models.HarmCategory.HARM_CATEGORY_HARASSMENT: generative_models.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
            }
        self.BUCKET_NAME = 'kunal_bucket_hckthn'
        self.image_path = ""
        self.generated_text = ""

    # Upload image to GCS bucket
    def upload_image_to_gcs(self, image_file):
        bucket = client.bucket(self.BUCKET_NAME)
        filename = image_file.filename
        blob = bucket.blob(filename)
        blob.upload_from_string(
            image_file.read(),
            content_type=image_file.content_type
        )
        return filename

    def language_translation(self, text, target_language):
        prompt = f"Translate the following text to {target_language}: {text}"
        responses = self.model.generate_content(
                    [prompt],
                    generation_config=self.generation_config,
                    safety_settings=self.safety_settings,
                    stream=True
                )
        translated_text = ""
        for response in responses:
            translated_text += response.text
        return translated_text

    def generate(self):
        if request.method == 'POST':
            prompt = request.form['prompt']
            image_file = request.files['image']
            try:
                image_name = self.upload_image_to_gcs(image_file)
                image_bkt_path = f"gs://{self.BUCKET_NAME}/{image_name}"
                image = Part.from_uri(image_bkt_path, mime_type="image/jpeg")
                self.image_path = f"https://storage.googleapis.com/{self.BUCKET_NAME}/{image_name}"

                responses = self.model.generate_content(
                    [f"{prompt}", image],
                    generation_config=self.generation_config,
                    safety_settings=self.safety_settings,
                    stream=True
                )
                self.generated_text = ""
                for response in responses:
                    self.generated_text += response.text

                return render_template('result.html', generated_text=self.generated_text, image_path=self.image_path, error=None)
            except Exception as e:
                error = str(e)
                return render_template('index.html', error=error)
        elif request.method == 'GET':
            try:
                language = request.args.get('language')
                if language:
                    self.generated_text = self.language_translation(self.generated_text, language)
                    return render_template('result.html', generated_text=self.generated_text, image_path=self.image_path, error=None)
                return redirect(url_for('index'))
            except Exception as e:
                error = str(e)
                return render_template('index.html', error=error)

my_app = MyApp()

@app.route('/')
def index():
    return render_template('index.html', error=None)

@app.route('/generate', methods=['POST', 'GET'])
def generate():
    return my_app.generate()


if __name__ == '__main__':
    app.run(debug=True, port=8000)
