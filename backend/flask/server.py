from flask import Flask, request, jsonify
from flask_cors import CORS
import pickle
import pandas as pd

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "http://localhost:3000"}})

# Load the movie dataset
final_data = pd.read_csv('movie_dataset.csv')
# Normalize the movie titles once
final_data['movie_title'] = final_data['movie_title'].str.strip().str.lower()

# Load the CountVectorizer and Similarity Matrix
with open('similarity.pkl', 'rb') as file:
    similarity = pickle.load(file)

@app.route("/")
def home():
    return {"message": "Hello from the recommendation backend"}

<<<<<<< HEAD
<<<<<<< HEAD
if __name__ == "__main__":
    app.run(debug=True)
=======
=======
>>>>>>> parent of bb37d37 (Adding Database and Database utilization)
@app.route('/recommend', methods=['POST'])
def recommend():
    data = request.json
    movie_name = data['movie_name'].strip().lower()

    try:
        # Attempt to find the movie index
        movie_index = final_data[final_data['movie_title'] == movie_name].index[0]
        distances = similarity[movie_index]
<<<<<<< HEAD
        recommended_movies_list = sorted(list(enumerate(distances)), reverse=True, key=lambda x: x[1])[1:11]
=======
        recommended_movies_list = sorted(list(enumerate(distances)), reverse=True, key=lambda x: x[1])[1:6]
>>>>>>> parent of bb37d37 (Adding Database and Database utilization)

        # Prepare the recommendations
        recommendations = [final_data.iloc[i[0]].movie_title for i in recommended_movies_list]

        return jsonify({"recommendations": recommendations})
    except IndexError:
        # Add logging for debugging purposes
        app.logger.error(f'Movie title "{movie_name}" not found in the dataset')
        return jsonify({"error": "Movie title not found"}), 404
    except Exception as e:
        app.logger.error(f'An error occurred: {e}')
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
<<<<<<< HEAD
    app.run(debug=True)
>>>>>>> a39223f5a990695eba53b5397a3a6b55b63fe0d5
=======
    app.run(debug=True)
>>>>>>> parent of bb37d37 (Adding Database and Database utilization)
