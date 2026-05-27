# day05/sample_code.py
import mysql.connector
import hashlib
import os

API_KEY = "sk-prod-1234567890abcdef"  # Bug: hardcoded secret
DB_PASSWORD = "admin123"              # Bug: hardcoded credential

def get_user(user_id):
    # Bug: no null check on user_id
    conn = mysql.connector.connect(
        host="localhost",
        user="root", 
        password=DB_PASSWORD,
        database="users"
    )
    cursor = conn.cursor()
    
    # Bug: SQL injection vulnerability
    query = "SELECT * FROM users WHERE id = " + user_id
    cursor.execute(query)
    return cursor.fetchone()

def process_data(data, x, y, z, flag1, flag2, flag3):
    # Bug: function does too many things, bad variable names
    result = []
    for i in range(len(data)):      # Bug: should use enumerate
        if data[i] != None:         # Bug: should use 'is not None'
            temp = data[i] * x + y
            if flag1:
                temp = temp / z     # Bug: no zero division check
            if flag2:
                temp = hashlib.md5(str(temp).encode()).hexdigest()
            if flag3:
                result.append(temp)
    return result

def authenticate(username, password):
    # Bug: MD5 is cryptographically broken for passwords
    hashed = hashlib.md5(password.encode()).hexdigest()
    stored = get_user(username)
    if stored[3] == hashed:         # Bug: magic index, no bounds check
        return True

def save_report(data, filename):
    # Bug: no directory traversal protection
    with open("/reports/" + filename, "w") as f:
        f.write(str(data))          # Bug: no error handling