from flask import Flask, request, jsonify
import pandas as pd
import requests
import io
import PyPDF2
import mimetypes
from PyPDF2 import PdfReader  # Updated for PdfReader

app = Flask(__name__)

@app.route('/read-file', methods=['POST'])
def read_file():
    try:
        # Get the links from the request
        urls = request.json.get('urls')

        if not urls or len(urls) < 1:
            return jsonify({'error': 'No URLs provided'}), 400

        response = None

        # Try each URL until one works
        for url in urls:
            try:
                # Convert Google Drive links to direct download links if applicable
                if 'drive.google.com/file/d/' in url:
                    file_id = url.split('/d/')[1].split('/')[0]
                    url = f'https://drive.google.com/uc?export=download&id={file_id}'
                elif 'drive.google.com/open?id=' in url:
                    file_id = url.split('id=')[1]
                    url = f'https://drive.google.com/uc?export=download&id={file_id}'

                # Download the file
                response = requests.get(url)
                response.raise_for_status()  # Ensure we got a successful response
                break  # If successful, break out of the loop
            except requests.exceptions.RequestException as e:
                # Log the error and continue to the next URL
                print(f"Failed to download from {url}: {str(e)}")
                continue

        if response is None:
            return jsonify({'error': 'All provided URLs failed to download'}), 400

        # Get the content type from the response headers
        content_type = response.headers.get('Content-Type')
        extension = mimetypes.guess_extension(content_type)

        detected_content_type = content_type  # Use content type from response headers if available

        # Process the file based on the content type or extension
        if detected_content_type == 'text/csv' or extension == '.csv':
            # If the URL points to a CSV file
            file = io.StringIO(response.text)
            df = pd.read_csv(file)

        elif detected_content_type in ['application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 'application/vnd.ms-excel'] or extension in ['.xlsx', '.xls']:
            # If the URL points to an Excel file
            file = io.BytesIO(response.content)
            df = pd.read_excel(file, engine='openpyxl')

        elif detected_content_type == 'application/json' or extension == '.json':
            # If the URL points to a JSON file
            df = pd.read_json(io.StringIO(response.text))

        elif detected_content_type == 'text/plain' or extension == '.txt':
            # If the URL points to a TXT file
            file = io.StringIO(response.text)
            df = pd.read_table(file, delimiter=',')  # Adjust delimiter as needed

        elif 'docs.google.com/spreadsheets' in url:
            # Handle Google Sheets URL
            file_id = url.split('/d/')[1].split('/')[0]
            csv_url = f'https://docs.google.com/spreadsheets/d/{file_id}/export?format=csv'
            response = requests.get(csv_url)
            response.raise_for_status()  # Ensure we got a successful response
            csv_file = io.StringIO(response.text)
            df = pd.read_csv(csv_file)

        elif detected_content_type == 'application/pdf' or extension == '.pdf':
            # If the URL points to a PDF file
            file = io.BytesIO(response.content)
            pdf_reader = PdfReader(file)
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
            # Return the extracted text from PDF
            return jsonify({'pdf_text': text})

        elif detected_content_type == 'application/octet-stream' or extension == '.bin':
            # Handle ambiguous file types or binary files
            # Attempt different file types (Excel, PDF)
            try:
                # Try to read it as an Excel file
                file = io.BytesIO(response.content)
                df = pd.read_excel(file, engine='openpyxl')
            except Exception as e:
                print(f"Failed to read as Excel: {str(e)}")
                try:
                    # Try to read it as a PDF file
                    file.seek(0)
                    pdf_reader = PdfReader(file)
                    text = ""
                    for page in pdf_reader.pages:
                        text += page.extract_text() + "\n"
                    # Return the extracted text from PDF
                    return jsonify({'pdf_text': text})
                except Exception as e:
                    print(f"Failed to read as PDF: {str(e)}")
                    # Fallback to returning raw data
                    return jsonify({'error': 'Unsupported or unknown file type', 'content_type': content_type, 'details': 'Could not parse the file content'}), 400

        else:
            return jsonify({'error': 'Unsupported file type', 'content_type': content_type, 'extension': extension, 'detected_content_type': detected_content_type}), 400

        return jsonify(df.to_dict())
    
    except requests.exceptions.RequestException as e:
        # Handle request errors (e.g., bad response)
        return jsonify({'error': 'Request failed', 'details': str(e)}), 500
    except Exception as e:
        # Handle other errors (e.g., parsing errors)
        return jsonify({'error': 'An error occurred', 'details': str(e)}), 500

if __name__ == '__main__':
    app.run()