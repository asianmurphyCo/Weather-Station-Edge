import mysql.connector
import pymongo
import time
import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion
import json
from config import mqtt_host, mqtt_port, mqtt_topic, mongodb_host, mongodb_dbname, mysql_host, mysql_user, mysql_password, mysql_database

# Open database connections at the start
print("Connecting to MySQL database")
db_connection = mysql.connector.connect(
    host=mysql_host,
    user=mysql_user,
    password=mysql_password,
    database=mysql_database
)
print("Connected to MySQL database")

print("Connecting to Mongo database")
myclient = pymongo.MongoClient(mongodb_host)
mydb = myclient[mongodb_dbname]
mycol = mydb["WeatherStation"]
print("Connected to Mongo database")

# Function to check internet connection
def is_internet_connected():
    return True

# Function to check if a document already exists in MongoDB
def is_duplicate_document(document):
    existing_doc = mycol.find_one({"recordID": document["recordID"]})
    return existing_doc is not None

# Function to check and sync the latest 5 data between MongoDB and MySQL
def check_and_sync_data():
    mycursor = db_connection.cursor(dictionary=True)
    mycursor.execute("SELECT * FROM weather_data ORDER BY recordID DESC LIMIT 5")
    rows = mycursor.fetchall()

    for row in rows:
        document = {
            "recordID": row["recordID"],
            "recordDate": row["recordDate"].strftime('%Y-%m-%d'),
            "recordTime": str(row["recordTime"]),
            "temp": row["temp"],
            "humidity": row["humidity"],
            "baroPressure": row["baroPressure"],
            "windDirect": row["windDirect"],
            "avgWindSpd": row["avgWindSpd"],
            "mxWindSpd": row["mxWindSpd"],
            "rainPerHr": row["rainPerHr"],
            "rainPerDay": row["rainPerDay"]
        }

        # If the document does not exist in MongoDB, insert it
        if not is_duplicate_document(document):
            mycol.insert_one(document)
            print("Document inserted into MongoDB.")
        else:
            print("Document already exists in MongoDB. Skipped insertion.")

    print("Data sync completed.")
    mycursor.close()

# Callback function to handle incoming MQTT messages
def on_message(client, userdata, msg):
    topic = msg.topic
    message = msg.payload.decode("utf-8")

    data = json.loads(message)
    temp = float(data["temperature"])
    humidity = float(data["humidity"])
    baroPressure = float(data["pressure"])
    windDirect = float(data["windDirection"])
    avgWindSpd = float(data["windSpeedAvg"])
    mxWindSpd = float(data["windSpeedMax"])
    rainPerHr = float(data["rainfall_H"])
    rainPerDay = float(data["rainfall_D"])

    mycursor = db_connection.cursor(dictionary=True)

    # Insert the data into MySQL
    insert_query = "INSERT INTO weather_data (temp, humidity, baroPressure, windDirect, avgWindSpd, mxWindSpd, rainPerHr, rainPerDay) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"
    insert_values = (temp, humidity, baroPressure, windDirect, avgWindSpd, mxWindSpd, rainPerHr, rainPerDay)
    mycursor.execute(insert_query, insert_values)
    db_connection.commit()

    document = {
        "recordID": mycursor.lastrowid,
        "recordDate": time.strftime('%Y-%m-%d'),
        "recordTime": time.strftime('%H:%M:%S'),
        "temp": temp,
        "humidity": humidity,
        "baroPressure": baroPressure,
        "windDirect": windDirect,
        "avgWindSpd": avgWindSpd,
        "mxWindSpd": mxWindSpd,
        "rainPerHr": rainPerHr,
        "rainPerDay": rainPerDay
    }

    # If the document does not exist in MongoDB, insert it
    if not is_duplicate_document(document):
        mycol.insert_one(document)
        print("Message inserted into MySQL and MongoDB.")
    else:
        print("Duplicate document. Skipped insertion.")

    mycursor.close()

    # Check and sync data after every 5 insertions
    if mycursor.lastrowid % 5 == 0:
        check_and_sync_data()

# Create MQTT client and set callback function
client = mqtt.Client(CallbackAPIVersion.VERSION2)
client.on_message = on_message

# Connect to MQTT broker and subscribe to topic
client.connect(mqtt_host, mqtt_port)
client.subscribe(mqtt_topic)

# Check and sync data if internet is connected
if is_internet_connected():
    check_and_sync_data()

# Start the MQTT client loop
try:
    client.loop_start()
    while True:
        time.sleep(5)
finally:
    # Stop the loop and close database connections at the end
    client.loop_stop()
    db_connection.close()
    myclient.close()
