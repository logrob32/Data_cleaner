from flask import Flask, request, send_file, render_template
import os
from werkzeug.utils import secure_filename
from toast_cleaner_v5 import clean_data

app = Flask(__name__)

@app.route('/')
def index():
    # This will render the 'index.html' file when the home route is accessed
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def process_data():
    uploaded_file = request.files['data']
    city = request.form['city']
    state = request.form['state']
    output_name = request.form['output_name'] if 'output_name' in request.form else 'cleaned_data'

    if uploaded_file and output_name:
        filename = secure_filename(uploaded_file.filename)
        data_path = os.path.join('uploads', filename)
        uploaded_file.save(data_path)

        try:
            cleaned_data = clean_data(data_path, city, state)
            cleaned_data_csv = f"{output_name}.csv"
            cleaned_data.to_csv(cleaned_data_csv, index=False)
            return send_file(cleaned_data_csv, as_attachment=True)
        except Exception as e:
            return f"An error occurred: {e}"
    else:
        return 'No file uploaded or output name provided.'

if __name__ == '__main__':
    # Create 'uploads' directory if it does not exist
    if not os.path.isdir('uploads'):
        os.mkdir('uploads')

    app.run(debug=True)
