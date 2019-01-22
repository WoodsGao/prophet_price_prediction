from flask import Flask, session, abort, redirect, flash, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin, LoginManager, login_required, login_user
from flask_wtf import FlaskForm
from flask_bootstrap import Bootstrap
from wtforms import StringField, PasswordField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Length
import os
import json
import time
from werkzeug.security import generate_password_hash, check_password_hash
import pandas as pd
import numpy as np
from fbprophet import Prophet
import requests
import datetime
from threading import Thread

class PredictThread():

    def __init__(self, symbol, period, interval):
        self.symbol = symbol
        self.period = period
        self.interval = interval

    def predict(self):
        try:
            r = requests.get('https://api.huobi.pro/market/history/kline?symbol=%s&period=%s&size=2000' % (self.symbol, self.period))
            obj = json.loads(r.text)['data']
            start = obj[-1]['id']
            interval = abs(obj[1]['id'] - obj[0]['id'])
            ds = [datetime.datetime.fromtimestamp(obj[0]['id']-i*24*60*60).strftime("%Y-%m-%d") for i in range(len(obj))]
            ds.reverse()
            y = [o['close'] for o in obj]
            y.reverse()
            df = pd.DataFrame({'ds':ds, 'y':y})

            m = Prophet()
            m.fit(df)

            future = m.make_future_dataframe(periods=7*24)

            forecast = m.predict(future)
            # print(forecast.tail())
            forecast['trend_upper'] = forecast['trend_upper'] - forecast['trend_lower']
            result = {}
            result['ds'] = [datetime.datetime.fromtimestamp(start + i * interval).strftime("%m-%d %H:%M") for i in range(forecast.shape[0])]
            result['trend'] = forecast['trend'].tolist()
            result['trend_upper'] = forecast['trend_upper'].tolist()
            result['trend_lower'] = forecast['trend_lower'].tolist()
            result['origin'] = y
            with open('data/%s_%s' % (self.symbol, self.period), 'w') as f:
                f.write(json.dumps(result))
            return 1
        except Exception as e:
            print(e)
            # print(r.text)
            return 0

    def run_thread(self):
        if self.interval > 0:
            while 1:
                if self.predict():
                    time.sleep(self.interval)
                else:
                    time.sleep(60)
        else:
            self.predict()

    def run(self):
        t = Thread(target=self.run_thread)
        t.setDaemon(True)
        t.start()

app = Flask(__name__)
app.config['DEBUG'] = False
app.config['SECRET_KEY'] = '32489r32hjd982h'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///data.sqlite'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

bootstrap = Bootstrap(app)

login_manager = LoginManager(app)
login_manager.login_view = 'login'

symbols = ['btcusdt','ethusdt', 'eosusdt', 'neousdt', 'htusdt']
periods = ['15min', '60min', '1day']
#symbols=['btcusdt']
#periods=['1day']
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, index=True)
    password_hash = db.Column(db.String(128))

    # read(unreadable)
    @property
    def password(self):
        raise AttributeError('password is not a readable attribute')

    # write
    @password.setter
    def password(self, password):
        self.password_hash = generate_password_hash(password)

    def verify_password(self, password):
        return check_password_hash(self.password_hash, password)

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(1,64)])
    password = PasswordField('Password', validators=[DataRequired(), Length(8,16)])
    submit = SubmitField('Log In')

@app.route('/', methods=['GET'])
def home():
    return render_template('home.html', symbols=symbols, periods=periods)

@app.route('/predict/<string:symbol>/<string:period>', methods=['GET'])
def predict(symbol, period):
    symbol = symbol.lower()
    if symbol not in symbols:
        abort(404)
    if period not in periods:
        abort(404)
    with open('data/%s_%s' % (symbol, period), 'r') as f:
        data = json.loads(f.read())
    return render_template('predict.html', symbols=symbols, periods=periods, data=data)

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and user.verify_password(form.password.data):
            login_user(user)
            return redirect('/')
        flash('Invalid username or password')
    return render_template('login.html', form=form, symbols=symbols, periods=periods)

@app.route('/manage', methods=['GET', 'POST'])
@login_required
def manage():
    return 'wait for it'


if __name__ == "__main__":
    for s in symbols:
        for p in periods:
            t = PredictThread(s, p, 300)
            t.run()
            time.sleep(1)
    app.run(host='0.0.0.0', port=5000)
    input()
    

