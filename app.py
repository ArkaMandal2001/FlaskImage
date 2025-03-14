from flask import Flask,render_template,request,redirect,url_for,Response
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager,UserMixin,login_user,login_required,logout_user,current_user
from flask_wtf import FlaskForm
from wtforms import StringField,PasswordField,SubmitField,IntegerField
from wtforms.validators import InputRequired,Length,ValidationError
from flask_bcrypt import Bcrypt
from werkzeug.utils import secure_filename
import uuid
import boto3
import psycopg2 
import keys

app=Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI']=keys.FLASK_SQLALCHEMY_DATABASE_URI
app.config['SECRET_KEY'] = keys.FLASK_SECRET_KEY
db=SQLAlchemy(app)
bcrypt=Bcrypt(app)

login_manager=LoginManager()
login_manager.init_app(app)
login_manager.login_view='home'

#postgres Connection
conn = psycopg2.connect(database=keys.POSTGRES_DATABASE, user=keys.POSTGRES_USER, password=keys.POSTGRES_PASSWORD, host=keys.POSTGRES_HOST, port=keys.POSTGRES_PORT)
#s3 Connection
s3 = boto3.client('s3',region_name=keys.S3_REGION, aws_access_key_id=keys.S3_ACCESS_KEY, aws_secret_access_key=keys.S3_SECRET_KEY)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

#app.app_context().push()

class User(UserMixin,db.Model):
    id=db.Column(db.Integer,primary_key=True)
    username=db.Column(db.String(50),unique=True, nullable=False)
    password=db.Column(db.String(100),nullable=False)

class SignUpForm(FlaskForm):
    username=StringField('username',validators=[InputRequired(),Length(min=4,max=50)])
    password=PasswordField('password',validators=[InputRequired(),Length(min=8,max=20)])
    submit=SubmitField('Sign Up')
    def validate_username(self,username):
        user=User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('Username already exists')

class LogInForm(FlaskForm):
    username=StringField('username',validators=[InputRequired(),Length(min=4,max=50)])
    password=PasswordField('password',validators=[InputRequired(),Length(min=8,max=20)])
    submit=SubmitField('Log In')

@app.route('/',methods=['GET','POST'])
def home():
    loginForm=LogInForm()
    if loginForm.validate_on_submit():
        user=User.query.filter_by(username=loginForm.username.data).first()
        if user and bcrypt.check_password_hash(user.password,loginForm.password.data):
            login_user(user)
            return redirect(url_for('home'))
    if request.method=='POST':
        file = request.files['file']
        cur = conn.cursor()
        originalFileName=file.filename
        uploadedFileName=uuid.uuid4().hex+"."+originalFileName.rsplit('.', 1)[1]
        command="INSERT INTO metadata (imageOriginalName, imageUploadName, userID) VALUES ('%s', '%s', %s)" %(originalFileName, uploadedFileName,current_user.id)#any other metadata can be uploaded here
        #print(command)
        cur.execute(command)
        filename=secure_filename(originalFileName)
        file.save(filename)
        s3.upload_file(filename, keys.S3_BUCKET_NAME, uploadedFileName)
        conn.commit()
        return redirect(url_for('home'))
    if current_user.is_authenticated:
        cur = conn.cursor()
        cur.execute("SELECT imageOriginalName, imageUploadName FROM metadata WHERE userID=%s" %current_user.id)
        data = cur.fetchall()
        #s3.download_file('BUCKET_NAME', 'OBJECT_NAME', 'FILE_NAME')
        return render_template('home.html',loginForm=loginForm,data=data)
    return render_template('home.html',loginForm=loginForm)

@app.route('/signUp',methods=['GET','POST'])
def signUp():
    form=SignUpForm()
    if form.validate_on_submit():
        hashed_password=bcrypt.generate_password_hash(form.password.data)
        user=User(username=form.username.data,password=hashed_password)
        db.session.add(user)
        db.session.commit()
        return redirect(url_for('home'))
    return render_template('signUp.html',form=form)

@app.route('/download/<objectName>/<originalName>',methods=['GET'])
@login_required
def download(objectName,originalName):
    cur = conn.cursor()
    cur.execute("SELECT userID FROM metadata WHERE imageUploadName='%s'" %objectName)
    data = cur.fetchall()
    if data[0][0]!=current_user.id:
        return redirect(url_for('home'))
    else:
        file = s3.get_object(Bucket=keys.S3_BUCKET_NAME, Key=objectName)
        return Response(
            file['Body'].read(),
            mimetype='text/plain',
            headers={"Content-Disposition": "attachment;filename=%s" % originalName})

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))

if __name__ == '__main__':
    #ssl context given here
    app.run(debug=True)