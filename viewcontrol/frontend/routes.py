from . import bp
from flask import render_template, flash, redirect, url_for
from flask import current_app as app
from .forms import AddShow

@bp.route('/')
@bp.route('/index')
def index():
    return render_template('index.html' , show=app.meineshow)    

@bp.route('/show/<showname>')
def show(showname):
    app.meineshow.show_load(showname)
    return render_template('show.html', show=app.meineshow)

@bp.route('/add_show', methods=['GET', 'POST'])
def add_show():
    form = AddShow()
    if form.validate_on_submit():
        app.meineshow.show_new(form.showname.data)
        app.meineshow.module_add_text('DeinErstesElement', 'Hallo Zusammen', 10)
        flash("Die Show wurde erstellt.")
        return redirect(url_for('.index'))
    return render_template('add_show.html', form=form)