import os
import jinja2
import webapp2
import Cookie

from google.appengine.ext import db

template_dir = os.path.join(os.path.dirname(__file__), 'layouts')
jinja_env = jinja2.Environment(loader = jinja2.FileSystemLoader(template_dir), autoescape= True)

import hmac
SECRET = "twiscode"

#Defining user status, if logged in show a greeting
not_logged_in = "<li><a href="'/signup'">Register</a></li><li><a href='/login'>Login</a></li>"
logged_in = "<li class='dropdown'><a href='' class='dropdown-toggle' data-toggle='dropdown' role='button' aria-haspopup='true' aria-expanded='false'>Hi, %s<span class='caret'></span></a><ul class='dropdown-menu'><li><a href='/logout'>Logout</a></li></ul></li>"

def hash_str(s):
    return hmac.new(SECRET, s).hexdigest()

def make_secure_val(s):
    return "%s|%s" % (s, hash_str(s))

def check_secure_val(h):
    val = h.split("|")[0]
    if h == make_secure_val(val):
        return val

def render_str(template, **params):
    t = jinja_env.get_template(template)
    return t.render(params)

class User(db.Model):
    username = db.StringProperty(required = True)
    email = db.StringProperty()
    password = db.StringProperty(required = True)

class Blogpost(db.Model):
    subject = db.StringProperty(required = True)
    content = db.TextProperty(required = True)
    date = db.DateTimeProperty(auto_now_add = True)
    author = db.ReferenceProperty(User)

    def render(self):
        self._render_text = self.content.replace('\n', '<br>')
        return render_str("post.html", blogpost = self, blogpost_link = '/%s' % str(self.key().id()))

    def render_single_post(self, user, error_like):
        self._render_text = self.content.replace('\n', '<br>')
        related_post = db.GqlQuery(' SELECT * FROM Blogpost WHERE author = :1 ', self.author)
        related = ''

        #fetching related post to be displayed at the page
        if related_post.count > 1:
            related = related_post.fetch(limit=5)
        else:
            related = None

        #checking if author is the same, only author can edit/delete the post
        isAuthor = False
        if user:
            if self.author.key().id() == user.key().id():
                isAuthor = True

        #getting total number of likes
        likes = db.GqlQuery(' SELECT * FROM LikePost WHERE blogpost = :1 ', self)
        numberOfLikes = likes.count()

        #getting total number of comments
        comments = db.GqlQuery(' SELECT * FROM Comment WHERE blogpost = :1 ', self)
        numberOfComments = comments.count()

        return render_str('single-post.html',
                        blogpost = self, blogpost_link = '/%s' % str(self.key().id()),
                        related = related,
                        isAuthor = isAuthor,
                        likeCounter = numberOfLikes,
                        commentCounter = numberOfComments,
                        error_like = error_like )

    def render_edit(self):
        self._render_text = self.content.replace('\n', '<br>')
        return render_str("editpost.html", blogpost = self)

#Defining Like Class
class LikePost(db.Model):
    user        = db.ReferenceProperty(User)
    blogpost    = db.ReferenceProperty(Blogpost)
    date        = db.DateTimeProperty(auto_now_add = True)

#Defining Comment class
class Comment(db.Model):
    user        = db.ReferenceProperty(User)
    blogpost    = db.ReferenceProperty(Blogpost)
    content     = db.TextProperty(required = True)
    date        = db.DateTimeProperty(auto_now_add = True)

class Handler(webapp2.RequestHandler):
    def write(self, *args, **kwargs):
        self.response.out.write(*args, **kwargs)

    def render_str(self, template, **params):
        temp = jinja_env.get_template(template)
        return temp.render(params)

    def render(self, template, **kwargs):
        self.write(self.render_str(template, **kwargs))

    #Getting user object from Cookie, cookie contains user id
    def get_user_object(self):
        cookie = self.request.cookies.get('user_id')
        if cookie:
            user_id = check_secure_val(cookie)

            if user_id:
                user_id = cookie.split('|')[0]
                key = db.Key.from_path('User', int(user_id))
                user = db.get(key)
                return user

    #Getting blogpost object from post id
    def get_blogpost(self, post_id):
        key = db.Key.from_path('Blogpost', int(post_id))
        blogpost = db.get(key)
        return blogpost

    def set_secure_cookie(self, name, val):
        cookie_val = make_secure_val(val)
        self.response.headers.add_header('Set-Cookie', '%s=%s; Path=/' % (name, cookie_val))

    def check_secure_cookie(self, name):
        cookie_val = self.request.cookies.get(name)
        return cookie_val and check_secure_val(cookie_val)

    #Getting login status to set the menu bar
    def get_login_status(self, user):
        status = ""
        if user:
            status = logged_in % user.username.upper()
        else:
            status = not_logged_in

        return status

    def login(self, user):
        self.set_secure_cookie('user_id', str(user.key().id()))

    def logout(self):
        self.response.headers.add_header('Set-Cookie', 'user_id=; Path=/')

class MainPage(Handler):
    def render_content(self, status = "" , contents = ""):
        contents = db.GqlQuery(" SELECT * from Blogpost "
                                " ORDER BY date DESC ")

        self.render("index.html", status = status, contents = contents)

    def get(self):
        user = self.get_user_object()
        if user:
            username = user.username
            status = logged_in % username.upper()
            self.render_content(status = status)

        else:
            status = not_logged_in
            self.render_content(status = status)

#Only author of the post is able to edit post, otherwise the edit button is not shown
class EditPost(Handler):
    def render_content(self, blogpost = "", error = ""):
        self.render("editpost.html", blogpost = blogpost, error = error)

    def get(self, post_id):
        blogpost = self.get_blogpost(post_id)

        user = self.get_user_object()
        author = blogpost.author
        if user:
            if author.key().id() == user.key().id() :
                self.render_content(blogpost = blogpost)
            else:
                self.redirect("/%s" % post_id)
        else:
            self.redirect("/login")

    def post(self, post_id):
        key = db.Key.from_path('Blogpost', int(post_id))
        blogpost = db.get(key)
        subject = self.request.get("subject")
        content = self.request.get("content")

        if subject and content:
            blogpost.subject = subject
            blogpost.content = content
            blogpost.put()
            self.redirect('/%s' % str(blogpost.key().id()))

#Same like edit, only author of the post is able to delete
class DeletePost(Handler):
    def get(self, post_id):
        blogpost = self.get_blogpost(post_id)

        user = self.get_user_object()
        author = blogpost.author
        if user:
            if author.key().id() == user.key().id() :
                blogpost.delete()
                self.redirect("/")
            else:
                self.redirect("/%s" % post_id)


class PostPage(Handler):
    def render_content(self, blogpost = "", content = "",user = "", comments = "", error_like = "", error_comment = "", status = ""):
        status = self.get_login_status(user)
        self.render("permalink.html", blogpost = blogpost, status = status, user = user, comments = comments, error_like = error_like, error_comment = error_comment)

    def get(self, post_id):
        blogpost = self.get_blogpost(post_id)
        user = self.get_user_object()
        if not blogpost:
            self.error(404)
            return

        if blogpost:
            cmt = db.GqlQuery(' SELECT * FROM Comment WHERE blogpost = :1 ', blogpost)
            comments = cmt.fetch(limit=None)
            self.render_content(blogpost = blogpost, user = user, comments = comments)

    def post(self, post_id):
        blogpost = self.get_blogpost(post_id)
        user = self.get_user_object()
        if user:
            if blogpost:
                #To detect which form is sent, the like or the comment
                if "likeBtn" in self.request.POST:
                    if blogpost.author.key().id() == user.key().id():
                        error = "You cannot like your own post!"
                        self.render_content(blogpost = blogpost, user = user, error_like = error)
                    else:
                        like = LikePost(user = user, blogpost = blogpost)
                        like.put()
                        self.redirect('/%s' % post_id)
                else:
                    content = self.request.get("comment")
                    if content:
                        comment = Comment(user = user, blogpost = blogpost, content = content)
                        comment.put()
                        self.redirect('/%s' % post_id)
                    else:
                        error = "Please write something before posting!"
                        self.render_content(blogpost = blogpost, user = user, error_comment = error)

        else:
            self.redirect("/login")

class NewPost(Handler):
    def render_content(self, subject = "", content = "", error = "", status = ""):
        self.render("newpost.html", subject = subject, content = content, error = error, status = status )

    def get(self):
        user = self.get_user_object()
        if user:
            self.render_content(status = logged_in % user.username.upper())

        else:
            self.render_content(status = not_logged_in)

    def post(self):

        user = self.get_user_object()

        if user:
            subject = self.request.get("subject")
            content = self.request.get("content")
            if subject and content:
                blogpost = Blogpost(subject = subject, content = content, author = user)
                blogpost.put()
                self.redirect('/%s' % str(blogpost.key().id()))
            else:
                error = "Please fill in both Title & Content!"
                self.render_content(subject = subject, content = content, error = error)

        else:
            error = "Please Login/Register before posting!"
            self.render_content(subject = "", content = "", error = error, status = not_logged_in)

class Signup(Handler):
    def render_content(self, username = "", password = "", email = "", error = "", status = ""):
        self.render("signup.html", username = username , password = password, email = email, error = error, status = status)

    def get(self):
        user = self.get_user_object()
        if user:
            self.redirect('/')
        else:
            self.render_content(status = not_logged_in)

    def post(self):
        username = self.request.get("username")
        password = self.request.get("password")
        verify   = self.request.get("verify")
        email    = self.request.get("email")

        if password != verify:
            error = "Password is not the same"
            self.render_content(username = username , password = password ,email = email, error = error )

        else:
            user = db.GqlQuery(" SELECT * FROM User WHERE username = :1 ", username )
            exist = user.count(limit=1)

            if exist:
                error = "Please choose another username"
                self.render_content(username = username , password = password ,email = email, error = error, status = not_logged_in)
            else:
                hashed_pwd = hash_str(password)
                new_user = User(username = username, email = email, password = hashed_pwd)
                new_user.put()

                self.login(new_user)
                self.redirect('/')

class Welcome(Handler):
    def get(self):
        cookie_val = self.check_secure_cookie('user_id')

        if cookie_val:
            user_id = cookie_val.split('|')[0]
            key = db.Key.from_path('User', int(user_id))
            user = db.get(key)
            username = user.username
            self.write("Welcome, %s" % username)
        else:
            self.redirect('/signup')

class Login(Handler):
    def render_content(self, username = "", password = "", error = "", status = ""):
        self.render("login.html", username = username, password = password, error = error, status = status)

    def get(self):
        user = self.get_user_object()
        if user:
            self.redirect('/')
        else:
            self.render_content(status = not_logged_in)

    def post(self):
        username = self.request.get("username")
        password = self.request.get("password")

        if username and password:
            hashed_pwd = hash_str(password)

            user_query = db.GqlQuery(" SELECT * FROM User WHERE username = :1 ", username )
            exist = user_query.count(limit=1)

            if exist:
                user = user_query.get()
                if user.password != hashed_pwd:
                    error = "Invalid Password"
                    self.render_content(username = username , password = "", error = error, status = not_logged_in)
                else:
                    self.login(user)
                    self.redirect("/")
            else:
                error = "Account does not exist! Please sign up first"
                self.render_content(username = username , password = "", error = error, status = not_logged_in)
        else:
            error = "Please fill in Username & Password"
            self.render_content(username = username , password = "", error = error)

class Logout(Handler):
    def get(self):
        self.logout()
        self.redirect('/')

app = webapp2.WSGIApplication([("/", MainPage),
                                ("/newpost", NewPost),
                                ("/([0-9]+)", PostPage),
                                ("/edit/([0-9]+)", EditPost),
                                ("/delete/([0-9]+)", DeletePost),
                                ("/signup", Signup),
                                ("/welcome", Welcome),
                                ("/login", Login),
                                ("/logout", Logout)], debug= True)



