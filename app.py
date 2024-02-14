# !pip install mysql-connector-python
#!conda install sqlalchemy -y
#!pip install --upgrade google-api-python-client 
#!pip install pymongo
#!pip install isodate


import streamlit as st
from bson import json_util

import json
from sqlalchemy import exc

from googleapiclient.discovery import build
from urllib.request import urlopen, HTTPError
from datetime import datetime
dt = datetime.strptime('1997-04-01','%Y-%m-%d')#CONVERTING STRING TO DATETIME OBJECT
import pymongo
from sqlalchemy import create_engine, text
from dateutil import parser
import isodate


connection_string = "mysql+mysqlconnector://root:borse123@127.0.0.1:3306/youtube"


# Set up the YouTube Data API
api_key = "AIzaSyA7_e8JxsZhY1L7gUMApyxMhUGkLcyn2L8"  # Replace with your actual API key
youtube = build("youtube", "v3", developerKey=api_key)



def get_channel_info(channel_id):
    response = youtube.channels().list(
        part="snippet,statistics,contentDetails",
        id=channel_id
    ).execute()

    # print(json.dumps(response, indent=4))
    channel_data = response["items"][0]

    channel_info = {
        "Channel_Name": {
            "Channel_Name": channel_data["snippet"]["title"],
            "Channel_Id": channel_id,
            "Subscription_Count": int(channel_data["statistics"]["subscriberCount"]),
            "Channel_Views": int(channel_data["statistics"]["viewCount"]),
            "Channel_Description": channel_data["snippet"]["description"],
            "Playlist_Id": channel_data["contentDetails"]["relatedPlaylists"]["uploads"]
        }
    }

    return channel_info

def get_video_info(video_id):
    response = youtube.videos().list(
        part="snippet,contentDetails,statistics",
        id=video_id
    ).execute()

    # print(json.dumps(response, indent=4))

    video_data = response["items"][0]


    Comments = {}
    try:
      # Get the comments for a video
      comments_response = youtube.commentThreads().list(
              part="snippet",
              videoId=video_id,
              maxResults=100,  # Adjust this value if needed
              textFormat="plainText"
          ).execute()

       # Extract comment information
      i =0
      for comment in comments_response["items"]:
          i=i+1
          # print(json.dumps(comment, indent=4))
          comment_data = comment["snippet"]["topLevelComment"]["snippet"]
          comment_info = {
                    "Comment_Id": comment["snippet"]["topLevelComment"]["id"],
                    "Comment_Text": comment_data["textDisplay"],
                    "Comment_Author": comment_data["authorDisplayName"],
                    "Comment_PublishedAt": comment_data["publishedAt"]
                }
          Comments['Comment_Id_'+str(i)]=comment_info

    except Error as e:
      print("An error occurred:", e)


    video_info = {
          "Video_Id": video_id,
          "Video_Name": video_data["snippet"]["title"],
          "Video_Description": video_data["snippet"]["description"],
          "Tags": video_data["snippet"]["tags"] if "tags" in video_data["snippet"] else [],
          "PublishedAt": video_data["snippet"]["publishedAt"],
          "View_Count": int(video_data["statistics"]["viewCount"]),
          "Like_Count": int(video_data["statistics"]["likeCount"]),
          # "Dislike_Count": int(video_data["statistics"]["dislikeCount"]),
          "Favorite_Count": int(video_data["statistics"]["favoriteCount"]),
          "Comment_Count": int(video_data["statistics"]["commentCount"]),
          "Duration": isodate.parse_duration(video_data["contentDetails"]["duration"]).total_seconds(),
          "Thumbnail": video_data["snippet"]["thumbnails"]["default"]["url"],
          "Caption_Status": video_data["contentDetails"]["caption"],
          "Comments": Comments
      }

    return video_info


def extract_data(channel_id):
    channel_info = get_channel_info(channel_id)

    playlist_id = channel_info["Channel_Name"]["Playlist_Id"]

    videos_response = youtube.playlistItems().list(
        part="contentDetails",
        playlistId=playlist_id,
        maxResults=50  # Adjust this value if needed
    ).execute()

    video_ids = [item["contentDetails"]["videoId"] for item in videos_response["items"]]

    i=0
    for video_id in video_ids:
        i = i+1
        video_info = get_video_info(video_id)
        channel_info['Video_Id_'+str(i)] = video_info

    return channel_info


client = pymongo.MongoClient("mongodb://localhost:27017/") #connect to local mangodb local host
mydb = client["youtubedb"]  #initialising the database
mycol = mydb["channel_details"]    #initialising the collection

engine = create_engine(connection_string, echo=True)


st.title("YouTube Data Harvesting and Warehousing using SQL, MongoDB and Streamlit")
st.header("... By Dr. Shubhangi Borse")
st.write("sample channel ids")

channels = ["UCwXAnR4X_KAY_NPs9pCPz1Q", "UCNU_lfiiWBdtULKOw6X0Dig", "UCDrf0V4fcBr5FlCtKwvpfwA", "UCCEN_eAgHIJLV792tr1aA0A", "UCh9nVJoWXmFb7sLApWGcLPQ", "UCeVMnSShP_Iviwkknt83cww", "UC0T6MVd3wQDB5ICAe45OxaQ", "UCK70H_67YRgeA513ZHA2TIg", "UC3SdeibuuvF-ganJesKyDVQ"]

if st.button("Delete All records in MongoDB"):
    mycol.delete_many({})
    
if st.button("Load 10 Channels info from Youtube to MongoDB"):
  with st.spinner('Wait for it...'):
    for channel_id in channels:
        
        details = extract_data(channel_id)
        status = mycol.insert_one(details)
        st.write("Channel Name "+ details["Channel_Name"]["Channel_Name"]+" saved into MongoDB")

st.write("MongoDB Records")
records = {}
result = mycol.find({},{"Channel_Name.Channel_Name": 1, "Channel_Name.Channel_Id": 1}).limit(30)
for row in result:
#    st.write(row)
   records[row["Channel_Name"]["Channel_Id"]] = row["Channel_Name"]["Channel_Name"]

st.table(records)

if st.button("Clear MySQL"):
    with engine.connect() as connection:
    
        connection.execute(text("SET FOREIGN_KEY_CHECKS = 0;"))
        connection.execute(text("TRUNCATE TABLE Comment;"))
        connection.commit()
        
        connection.execute(text("TRUNCATE TABLE Video;"))
        connection.commit()

        connection.execute(text("TRUNCATE TABLE Channel;"))
        
        connection.commit()
        connection.execute(text("TRUNCATE TABLE Playlist;"))
        connection.commit()
    st.write("MySQL tables are cleared")

bad_chars = [';', ':', '!', "*", "'", '(', ')',"\n"]


st.subheader("Data Migration to MySQL")
channel_id = st.text_input("Channel ID to migrate into MySQL")
if st.button("Migrate from MongoDb to MySQL"):
  with st.spinner('Wait for it...'):
    query = {}
    with engine.connect() as connection:
        connection.execute(text("SET FOREIGN_KEY_CHECKS = 0;"))
        connection.commit()

    query["Channel_Name.Channel_Id"]= channel_id
    result = mycol.find(query).limit(1)
   
    for json_dict in result:
        # with open('data.json', 'w') as f:
        #     json.dump(json.loads(json_util.dumps(row)),f)
        with engine.connect() as connection:
            desc = json_dict['Channel_Name']['Channel_Description'][:200].replace("'","")
        
            connection.execute(text(f"INSERT INTO `youtube`.`Channel` (`channel_id`, `channel_name`, `channel_view`, `channel_description`) VALUES ('{json_dict['Channel_Name']['Channel_Id']}', '{json_dict['Channel_Name']['Channel_Name']}', {json_dict['Channel_Name']['Subscription_Count']}, '{desc}');"))
            connection.commit()
            connection.execute(text(f"INSERT INTO `youtube`.`Playlist` (`playlist_id`, `channel_id`, `playlist_name`) VALUES('{json_dict['Channel_Name']['Playlist_Id']}', '{json_dict['Channel_Name']['Channel_Id']}', '{json_dict['Channel_Name']['Channel_Name']}');"))
            connection.commit()
            for key in json_dict.keys(): 
                if(key.startswith("Video_Id")):
               
        #//publish_date = datetime.strptime(json_dict[key]['PublishedAt'], '%Y-%m-%d %H:%M:%S')
                    publish_date = parser.isoparse(json_dict[key]['PublishedAt'])
                    video_desc = json_dict[key]['Video_Description'][:200].replace("'","")
                    try:
                        connection.execute(text(f"INSERT INTO `youtube`.`Video` (`video_id`, `playlist_id`, `video_name`, `video_description`, `published_date`, `view_coun`, `like_count`, `dislike_count`, `favorite_count`, `comment_count`) VALUES ('{json_dict[key]['Video_Id']}','{json_dict['Channel_Name']['Playlist_Id']}','{json_dict[key]['Video_Name']}', '{video_desc}', '{publish_date}','{json_dict[key]['View_Count']}','{json_dict[key]['Like_Count']}', 0, '{json_dict[key]['Favorite_Count']}', '{json_dict[key]['Comment_Count']}');"))

                        connection.commit()
                    except:
                        print('error')
                    
                    for comment_key in json_dict[key]['Comments'].keys():
                        comment = json_dict[key]['Comments'][comment_key]
                        comment_desc = comment['Comment_Text'][:200]

                        for i in bad_chars:
                            comment_desc = comment_desc.replace(i, '')
                        comment_publish_date = parser.isoparse(comment['Comment_PublishedAt'])

                        comment = json_dict[key]['Comments'][comment_key]
                        try:
                            
                            connection.execute(text(f"INSERT INTO `youtube`.`Comment` (`comment_id`, `video_id`, `comment_text`, `comment_author`, `comment_published_date`) VALUES ('{comment['Comment_Id']}','{json_dict[key]['Video_Id']}','{comment_desc}','{comment['Comment_Author']}','{comment_publish_date}');"))
                        except exc.SQLAlchemyError as e:
                            st.write(e)
                            print(comment_desc)
                    
                    connection.commit()
           
            st.write("Channel Name "+ json_dict['Channel_Name']['Channel_Name']+" saved into MySQL")

conn = st.connection(
    "local_db",
    type="sql",
    url=connection_string
)



    
    
# st.subheader("Channel Table")



# channel_df = conn.query("select * from Channel")
# st.dataframe(channel_df)

# st.subheader("Playlist Table")

# playlist_df = conn.query("select * from Playlist")
# st.dataframe(playlist_df)
        
# st.subheader("Video Table")
# video_df = conn.query("select * from Video")
# st.dataframe(video_df)


# st.subheader("Comment Table")
# comment_df = conn.query("select * from Comment")
# st.dataframe(comment_df)


st.subheader("Fetch Comments based on VideoID")
video_id = st.text_input("Video Id")
if st.button("Fetch Comments"):
    df = conn.query(f"SELECT Video.video_id,Comment.comment_text,Comment.comment_author FROM youtube.Comment JOIN youtube.Video on Comment.video_id = Comment.video_id and Comment.video_id='{video_id}'")
    st.dataframe(df)


st.write("1. What are the names of all the videos and their corresponding channels?")
if st.button("Answer 1"):
    st.write("SELECT Video.video_name, Channel.channel_name FROM Video INNER JOIN Playlist ON Video.playlist_id = Playlist.playlist_id INNER JOIN Channel ON Playlist.channel_id = Channel.channel_id ;")
    video_df = conn.query("SELECT Video.video_name, Channel.channel_name FROM Video INNER JOIN Playlist ON Video.playlist_id = Playlist.playlist_id INNER JOIN Channel ON Playlist.channel_id = Channel.channel_id ;")
    st.dataframe(video_df)
    

st.write("2. Which channels have the most number of videos, and how many videos do they have?")
if st.button("Answer 2"):
    st.write("SELECT Channel.channel_name, COUNT(Video.video_id) AS video_count FROM Video INNER JOIN Playlist ON Video.playlist_id = Playlist.playlist_id INNER JOIN Channel ON Playlist.channel_id = Channel.channel_id GROUP BY Channel.channel_name ORDER BY video_count DESC LIMIT 1;")
    video_df = conn.query("SELECT Channel.channel_name, COUNT(Video.video_id) AS video_count FROM Video INNER JOIN Playlist ON Video.playlist_id = Playlist.playlist_id INNER JOIN Channel ON Playlist.channel_id = Channel.channel_id GROUP BY Channel.channel_name ORDER BY video_count DESC LIMIT 1;")
    st.dataframe(video_df)
    
st.write("3.What are the top 10 most viewed videos and their respective channels?")
if st.button("Answer 3"):
    st.write("SELECT Video.video_name, Channel.channel_name, Video.view_coun as video_count FROM Video INNER JOIN Playlist ON Video.playlist_id = Playlist.playlist_id INNER JOIN Channel ON Playlist.channel_id = Channel.channel_id  ORDER BY video_count DESC LIMIT 10;")
    video_df = conn.query("SELECT Video.video_name, Channel.channel_name, Video.view_coun as video_count FROM Video INNER JOIN Playlist ON Video.playlist_id = Playlist.playlist_id INNER JOIN Channel ON Playlist.channel_id = Channel.channel_id  ORDER BY video_count DESC LIMIT 10;")
    st.dataframe(video_df)
    
st.write("4. How many comments were made on each video, and what are their corresponding video names?")
if st.button("Answer 4"):
    st.write("SELECT Video.video_name, COUNT(Comment.comment_id) AS comment_count FROM Video INNER JOIN Comment ON Video.video_id = Comment.video_id  GROUP BY Video.video_name ORDER BY comment_count DESC ;")
    video_df = conn.query("SELECT Video.video_name, COUNT(Comment.comment_id) AS comment_count FROM Video INNER JOIN Comment ON Video.video_id = Comment.video_id  GROUP BY Video.video_name ORDER BY comment_count DESC ;")
    st.dataframe(video_df)
    

    
st.write("5. Which videos have the highest number of likes, and what are their corresponding channel names?")
if st.button("Answer 5"):
    st.write("SELECT V.video_name, C.channel_name, V.like_count FROM Video V INNER JOIN Playlist P ON V.playlist_id = P.playlist_id INNER JOIN Channel C ON P.channel_id = C.channel_id ORDER BY V.like_count DESC LIMIT 10;")
    video_df = conn.query("SELECT V.video_name, C.channel_name, V.like_count FROM Video V INNER JOIN Playlist P ON V.playlist_id = P.playlist_id INNER JOIN Channel C ON P.channel_id = C.channel_id ORDER BY V.like_count DESC LIMIT 10;")
    st.dataframe(video_df)
    
    
st.write("6. What is the total number of likes and dislikes for each video, and what are  their corresponding video names?")
if st.button("Answer 6"):
    st.write("SELECT V.video_name,  V.like_count as like_count FROM Video V ORDER BY like_count DESC;")
    video_df = conn.query("SELECT V.video_name,  V.like_count as like_count FROM Video V ORDER BY like_count DESC;")
    st.dataframe(video_df)
    


st.write("7. What is the total number of views for each channel, and what are their corresponding channel names?")
if st.button("Answer 7"):
    st.write("SELECT c.channel_name, c.channel_view AS total_views FROM Channel c ORDER BY total_views DESC;")
    video_df = conn.query("SELECT c.channel_name, c.channel_view AS total_views FROM Channel c ORDER BY total_views DESC;")
    st.dataframe(video_df)
    

st.write("8. What are the names of all the channels that have published videos in the year 2022?")
if st.button("Answer 8"):
    st.write("SELECT V.video_name,  V.like_count as like_count FROM Video V ORDER BY like_count DESC;")
    video_df = conn.query("SELECT V.video_name,  V.like_count as like_count FROM Video V ORDER BY like_count DESC;")
    st.dataframe(video_df)
    
st.write("9. What is the average duration of all videos in each channel, and what are their corresponding channel names?")
if st.button("Answer 9"):
    st.write("SELECT c.channel_name, AVG(CASE WHEN v.duration IS NULL THEN 0 ELSE v.duration END) AS avg_duration FROM Video v INNER JOIN Playlist P ON V.playlist_id = P.playlist_id  INNER JOIN Channel c ON P.channel_id = c.channel_id GROUP BY c.channel_name ORDER BY avg_duration DESC;")
    video_df = conn.query("SELECT c.channel_name, AVG(CASE WHEN v.duration IS NULL THEN 0 ELSE v.duration END) AS avg_duration FROM Video v INNER JOIN Playlist P ON V.playlist_id = P.playlist_id  INNER JOIN Channel c ON P.channel_id = c.channel_id GROUP BY c.channel_name ORDER BY avg_duration DESC;")
    st.dataframe(video_df)
    
st.write("10. Which videos have the highest number of comments, and what are their corresponding channel names?")
if st.button("Answer 10"):
    st.write("SELECT V.video_name, C.channel_name, COUNT(Ch.comment_id) AS comment_count FROM Video V INNER JOIN Playlist P ON V.playlist_id = P.playlist_id   INNER JOIN Channel C ON P.channel_id = C.channel_id  INNER JOIN Comment Ch ON V.video_id = Ch.video_id  GROUP BY V.video_name, C.channel_name ORDER BY comment_count DESC;")
    video_df = conn.query("SELECT V.video_name, C.channel_name, COUNT(Ch.comment_id) AS comment_count FROM Video V INNER JOIN Playlist P ON V.playlist_id = P.playlist_id   INNER JOIN Channel C ON P.channel_id = C.channel_id  INNER JOIN Comment Ch ON V.video_id = Ch.video_id  GROUP BY V.video_name, C.channel_name ORDER BY comment_count DESC;")
    st.dataframe(video_df)
