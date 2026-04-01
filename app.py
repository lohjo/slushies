from flask import Flask, render_template

app = Flask(__name__)


@app.route("/")
def index():
    user_name = "Mustafa"
    return render_template("index.html", user_name=user_name)

@app.route("/testing")
def name():
    user_name = "Testing"
    return render_template("testing.html", user_name=user_name)

if __name__ == "__main__":
    app.run(port=5000, debug=True)