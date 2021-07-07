# Python program to read
# json file
  
import json

f = open ('params.json')

# Reading from file
data = json.loads(f.read())
  
print(data)
# Closing file
f.close()