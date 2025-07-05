---
layout: post
title: "parse don't validate in ruby: building safer applications"
date: 2025-07-05
categories: [ruby, patterns]
---

Dynamic languages like Ruby give you flexibility, but they also put the burden of data safety on you. Without compile-time type checking, how do you ensure your application doesn't crash when it receives unexpected data?

The answer is the "parse don't validate" pattern - a technique popularized by Alexis King's influential 2019 blog post that transforms unknown input into well-defined, validated objects before it reaches your business logic.

## the problem with validation-only approaches

Traditional validation approaches check if data is correct, but then continue working with the original, unstructured data:

```ruby
# Don't do this - validation without transformation
def create_user(params)
  if params[:email].present? && params[:name].present?
    User.create(params) # Still working with unstructured hash
    # What if params has unexpected keys?
    # What if email is nil despite the check?
    # What if someone changes the validation logic?
  end
end
```

This leaves you vulnerable to runtime errors when the raw data doesn't match your assumptions.

## parse don't validate: transform input into structured objects

Instead of just checking validity, transform unknown data into known, typed structures:

```ruby
class UserForm
  include ActiveModel::Model
  include ActiveModel::Attributes

  attribute :name, :string
  attribute :email, :string
  attribute :id, :integer

  validates :name, presence: true
  validates :email, presence: true, format: { with: URI::MailTo::EMAIL_REGEXP }
  validates :id, presence: true, numericality: { greater_than: 0 }

  def self.parse(data)
    form = new(data)
    raise ArgumentError, form.errors.full_messages.join(', ') unless form.valid?
    form
  end
end

# Usage
user_form = UserForm.parse(params) # Returns UserForm or raises
User.create!(user_form.attributes)
```

## why this pattern matters

1. **Explicit contracts** - Clear what each component expects and returns
2. **Fail fast** - Catch invalid data at system boundaries, not deep in business logic
3. **Self-documenting** - Code clearly shows what data flows through the system
4. **Centralized validation** - All validation rules in one place per data type
5. **Better error messages** - Specific, actionable feedback about what's wrong

## controllers: transform filtered params into validated objects

Strong parameters handle security (preventing mass assignment), but they still return unvalidated hashes. Add a parsing layer for data integrity:

```ruby
class UsersController < ApplicationController
  def create
    # Strong parameters filter, then parse for validation
    user_form = UserForm.parse(user_params)
    @user = UserCreationService.call(user_form)
    render json: UserSerializer.new(@user).to_h
  rescue ArgumentError => e
    render json: { error: e.message }, status: 422
  end

  private

  def user_params
    params.require(:user).permit(:name, :email, :id)
  end
end
```

## services: accept structured objects

Services should work with validated, structured data rather than raw hashes:

```ruby
class UserCreationService
  def self.call(user_form) # Explicit contract, not random hash
    user = User.create!(user_form.attributes)
    NotificationMailer.welcome_email(user).deliver_later
    user
  end
end
```

## external api integration

Transform external responses into internal objects to maintain consistent data contracts:

```ruby
class StripeChargeResult
  include ActiveModel::Model
  include ActiveModel::Attributes

  attribute :charge_id, :string
  attribute :amount_cents, :integer
  attribute :status, :string
  attribute :created_at, :datetime

  def self.from_stripe_response(response)
    new(
      charge_id: response[:id],
      amount_cents: response[:amount],
      status: response[:status],
      created_at: Time.at(response[:created])
    )
  end

  def successful? = status == 'succeeded'
  def amount_dollars = amount_cents / 100.0
end

# Usage
stripe_response = stripe_client.charges.create(charge_params)
charge_result = StripeChargeResult.from_stripe_response(stripe_response)

if charge_result.successful?
  record_payment(charge_result)
end
```

## background jobs: structured arguments

Instead of working with argument hashes, parse job parameters into validated objects:

```ruby
class EmailJobParams
  include ActiveModel::Model
  include ActiveModel::Attributes

  attribute :user_id, :integer
  attribute :template, :string, default: 'welcome'
  attribute :delay_minutes, :integer, default: 0

  validates :user_id, presence: true
  validates :template, inclusion: { in: %w[welcome premium reminder] }

  def self.parse(args)
    params = new(args)
    raise ArgumentError, params.errors.full_messages.join(', ') unless params.valid?
    params
  end

  def user
    @user ||= User.find(user_id)
  end
end

class WelcomeEmailJob < ApplicationJob
  def perform(raw_args)
    job_params = EmailJobParams.parse(raw_args)
    WelcomeMailer.send_email(job_params.user, job_params.template).deliver_now
  end
end
```

## alternative: result objects

For applications that prefer explicit success/failure handling over exceptions:

```ruby
require 'dry/monads'

class UserForm
  include Dry::Monads[:result]
  include ActiveModel::Model
  include ActiveModel::Attributes

  attribute :name, :string
  attribute :email, :string
  attribute :id, :integer

  validates :name, presence: true
  validates :email, format: { with: URI::MailTo::EMAIL_REGEXP }

  def self.safe_parse(data)
    form = new(data)
    return Failure(form.errors.full_messages) unless form.valid?
    Success(form)
  end
end

# Usage
case UserForm.safe_parse(params)
in Success(user_form)
  User.create!(user_form.attributes)
in Failure(errors)
  render json: { errors: errors }, status: 422
end
```

## libraries to consider

- `dry-validation` - Advanced validation with detailed error handling
- `dry-monads` - Result objects and functional patterns
- `dry-struct` - Immutable value objects with type coercion
- `reform` - Form objects that integrate seamlessly with Rails

## implementation strategy

1. **Start with new features** - Apply parsing pattern to all new controllers and services
2. **Focus on boundaries** - Prioritize user input, external APIs, and background jobs
3. **Refactor incrementally** - Convert existing code one component at a time

## the outcome

By parsing unknown data into known structures at every boundary, you eliminate a whole class of runtime errors. Your code becomes more predictable, easier to debug, and self-documenting.

In dynamic languages, explicit data contracts aren't just good practice - they're essential for building reliable applications that handle real-world data gracefully.