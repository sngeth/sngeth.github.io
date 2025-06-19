---
layout: post
title:  "Refactoring Part 1"
comments: true
categories: ["Ruby", "Refactoring"]
---
You may hear many developers groan at working on a legacy code base out
of control versus a greenfield project. However, I believe working in a
large legacy codebase provides a wonderful opportunity to improve your refactoring
skills.

This will be a series of connected blog posts on refactoring real world
code at my current job. I've attempted to obfuscate the code to make it
more generic and not tied to my company but the spirit should be the same.
Hopefully you are able to notice these issues in your own code and improve it.

So the first thing I did was run the flog gem(it essentially scores an
ABC metric: Assignments, Branches, Calls) on my app/ folder and
tackled the highest rated file which not suprisingly, was a controller:

```
91.1: flog total
91.1: flog/method average

91.1: RaterController#index            app/controllers/rater_controller.rb:3-2
```

I will go ahead and make the commentary before you look at the wall of
abomination. At first glance the code is so dense that it is not clear
at all what we're trying to do in the index action.

I hope this can convince you on the importance of having cleanly formatted code right off
the bat. While it's a very small file, it contains immense complexity.
The code smells I wanted to refactor in this first attempt:

1) Long method

It's a 24 line index action method. Cannot tell at
glance what it's doing.

2) Single Responsibility Principle violation

While it's reasonable to have a controller to delegate rating
different objects, it can get out of control to put that logic directly
in the controller. We could at first just perform Extract Method but
that would just be shuffling complexity within the file and does not let
us take advantage of fixing the next issue.

3) Case statement that type checks and Open/Close Principle Violation

We observe an if-else block that kept getting piled on as more domain
objects were needed to be rated


```ruby
class RaterController < AuthenticatedUserController

  def index
    @title = I18n.t 'rater.title'
    @active_rating   = manager_selection_is_self? ? params[:employee_rating   ] : params[:manager_rating]
    @inactive_rating = manager_selection_is_self? ? params[:manager_rating] : params[:employee_rating   ]
    @fullscreen_form_action = ''

    if params[:rated_item_type] == 'movies'
      movie = Movie.find(params[:id])
      @rated_item = MoviePresenter.new movie
      @fullscreen_form_action = rate_movie_path(id: movie.id, is_self: manager_selection_is_self?)
    elsif params[:rated_item_type] == 'books'
      book = Book.find(params[:id])

      ratee = manager_selection_is_self? ? current_user.id : selected_user.id
      rater = current_user.id

      @fullscreen_form_action = rate_book_path(id: Book.id, rater:rater, ratee: ratee, manager_rating: params[:manager_rating], employee_rating:params[:employee_rating])

      @rated_item = BookPresenter.new Book, selected_user_id: @selected_user_id
    elsif params[:rated_item_type] == 'restaurants'
      @fullscreen_form_action = rate_restaurants_path(id: selected_user.id, is_self: manager_selection_is_self?, rater_id: current_user.id, old_employee_rating: params[:employee_rating], old_manager_rating: params[:manager_rating])
      @rated_item = RestaurantRating.new(selected_user)
    end

    render layout: 'fullscreen_form_dialog'
  end

end
```

You probably didn't even bother to try and understand what was going on
above, huh? Here is the refactored code with changes in comments

```ruby
class RaterController < AuthenticatedUserController
  def index
    @title                  = I18n.t 'rater.title'
    @active_rating          = active_rating?
    @inactive_rating        = inactive_rating?
    @fullscreen_form_action = ''

    # Extracted logic to object_rater method to do all the work
    @fullscreen_form_action, @rated_item = object_rater
    render layout: 'fullscreen_form_dialog'
  end

  private

  # Use a rater "factory" to instantiate specific raters
  # Note we are using convention over configuration here:
  # We assume that we have classes with name DomainItemRate
  def object_rater
    object_rater_class.new(rating_params).call
  end

  # The if-else can be removed now since we have a factory
  # that knows how to instantiate itself based off item type.
  # This takes advantage of Ruby's dynamic dispatching instead
  # instead of needing to type check.
  def object_rater_class
    "#{params[:rated_item_type]}Rate".classify.constantize
  end

  # Instantiate a Parameter Object to pass to rater
  def rating_params
    "#{rating_type_rating}".classify.constantize.new(params)
  end

  # Remaining methods are helpers to parse params
  def active_rating?
    # return active rating check based on user
  end

  def inactive_rating?
    # return inactive rating check based on user
  end

  def id
    params['id'].to_i
  end

  def employee_rating
    params[:employee_rating]
  end

  def manager_rating
    params[:manager_rating]
  end

  def ratee
    # return the ratee
  end

  def rater
   # return the rater
  end
end
```

We don't have to modify the index action at all now and have a nice
convention for maintaining new Rater types. We simply just implement a
Rater class that "duck types" what the index action wants returned so we
can maintain Open/Close principles.

Example Rater Class:

```ruby
class BookRater
  def initialize(args)
    @id = args[:id].to_i
    @is_self = args[:is_self]
  end

  def call
    fullscreen_form_action = rate_book_path(id: book.id,
                                             is_self: @is_self)
    rated_item = BookPresenter.new book

    [fullscreen_form_action, rated_item]
  end

  private

  def book
    Book.find(id)
  end
end
```

Summary:
We broke out the rating logic for each domain type into plain old Ruby
objects(POROs) . We were able to instantiate these on the fly and remove
the if-else type checking by utilizing a factory pattern to dynamically dispatch to
our POROs.
