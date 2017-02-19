from google.appengine.ext import db
import os
import jinja2

template_dir = os.path.join(os.path.dirname(__file__), 'layouts')
jinja_env = jinja2.Environment(loader = jinja2.FileSystemLoader(template_dir), autoescape= True)


def render_str(template, **params):
        temp = jinja_env.get_template(template)
        return temp.render(params)

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