import requests

print("--- Testing Voice ---")
try:
    # Use any small valid wav file if possible, or just dummy bytes.
    # The server might fail before audio processing if the file is invalid, but it should still give an error message
    r = requests.post("http://127.0.0.1:8001/analyze", files={"audio": ("test.wav", b"RIFF$\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x02\x00\x10\x00data\x00\x00\x00\x00")})
    print(r.status_code)
    print(r.text)
except Exception as e:
    print(e)
    
print("--- Testing Video ---")
try:
    r = requests.post("http://127.0.0.1:8003/analyze", files={"video": ("test.webm", b"fakevideo")})
    print(r.status_code)
    print(r.text)
except Exception as e:
    print(e)
