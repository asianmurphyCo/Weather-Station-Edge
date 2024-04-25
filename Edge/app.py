from flask import Flask, render_template, request
import mysql.connector
from config import mysql_host, mysql_user, mysql_password, mysql_database

app = Flask(__name__)
app.debug = True

@app.route('/')
def dashboard():
    # Fetch data from the local MySQL database
    db_connection = mysql.connector.connect(
        host=mysql_host,
        user=mysql_user,
        password=mysql_password,
        database=mysql_database 
    )
    cursor = db_connection.cursor(dictionary=True)
    cursor.execute("SELECT * FROM weather_data")
    data = cursor.fetchall()
    cursor.close()
    db_connection.close()

    # Get the website URL from the request
    website_url = request.url

    # Determine the state of the website
    if data:
        website_state = "Data available"
    else:
        website_state = "No data"

    # Log the website URL and state
    log_message = f"Website URL: {website_url}, State: {website_state}"
    print(log_message)

    # Render the dashboard template with the data
    return render_template('dashboard.html', data=data)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)