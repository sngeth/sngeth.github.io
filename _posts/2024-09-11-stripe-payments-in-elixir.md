---
layout: post
title: "Implementing Stripe Payments in Phoenix 1.7 with Stripity Stripe"
category: "Elixir"
comments: true
---
This guide outlines the process of integrating Stripe payments into a Phoenix 1.7 application using the Stripity Stripe library. It covers the key steps in implementation and highlights the differences in Phoenix 1.7's architecture that may affect the integration process.

## Advantages of Stripity Stripe

Stripity Stripe offers several benefits for handling payments in Elixir:

1. **Elixir-native implementation**: Designed specifically for use with Elixir.
2. **Comprehensive coverage**: Supports most features of the Stripe API.
3. **Regular maintenance**: Kept up-to-date with Stripe's API changes.
4. **Type safety**: Utilizes Elixir's type system to reduce runtime errors.

Compared to manual API integration, Stripity Stripe simplifies API calls, webhook handling, and error management.

## Architectural Changes in Phoenix 1.7

Phoenix 1.7 introduces several changes to the framework's structure:

1. **Function Components**: Replaces traditional templates with function components in a dedicated HTML module.
2. **Embedded Templates**: Templates are now embedded directly in the HTML module using `embed_templates "*.html"`.
3. **Updated Path Helpers**: The `~p` sigil replaces the previous `Routes.x_path` syntax.

These changes affect how views and templates are structured and how routes are referenced within the application.

## Implementation Steps

### 1. Project Setup

Add Stripity Stripe to your `mix.exs`:

```elixir
{:stripity_stripe, "~> 2.0"}
```

Run `mix deps.get` to install the dependency.

### 2. Stripe Configuration

In `config/config.exs`, add:

```elixir
config :stripity_stripe, api_key: System.get_env("STRIPE_SECRET_KEY")
```

### 3. Create and Run Migration

Before setting up the controller, we need to create a database table to store payment information. Let's create a migration:

```bash
mix ecto.gen.migration create_payments
```

This will create a new migration file in the `priv/repo/migrations` directory. Open the newly created file and add the following content:

```elixir
defmodule YourApp.Repo.Migrations.CreatePayments do
  use Ecto.Migration

  def change do
    create table(:payments) do
      add :amount, :integer
      add :stripe_id, :string
      add :status, :string

      timestamps()
    end

    create index(:payments, [:stripe_id])
  end
end
```

This migration creates a `payments` table with fields for the amount, Stripe ID, and status of the payment. The `timestamps()` function adds `inserted_at` and `updated_at` fields.

Now, run the migration:

```bash
mix ecto.migrate
```

### 4. Create Payment Schema

After creating the database table, we need to define a schema for it. Create a new file `lib/your_app/payments/payment.ex`:

```elixir
defmodule YourApp.Payments.Payment do
  use Ecto.Schema
  import Ecto.Changeset

  schema "payments" do
    field :amount, :integer
    field :stripe_id, :string
    field :status, :string

    timestamps()
  end

  def changeset(payment, attrs) do
    payment
    |> cast(attrs, [:amount, :stripe_id, :status])
    |> validate_required([:amount, :stripe_id, :status])
  end
end
```

This schema corresponds to the database table we just created and provides a changeset function for validating and casting payment data.
### 5. Payment Controller

Create `lib/your_app_web/controllers/payment_controller.ex`:

```elixir
defmodule YourAppWeb.PaymentController do
  use YourAppWeb, :controller
  alias YourApp.Payments.Payment

  def new(conn, _params) do
    changeset = Payment.changeset(%Payment{}, %{})
    stripe_publishable_key = Application.get_env(:liftforge, :stripe_publishable_key)
    render(conn, :new, changeset: changeset, stripe_publishable_key: stripe_publishable_key)
  end

  def create(conn, %{"payment" => payment_params}) do
    amount = payment_params["amount"]
    token = payment_params["token"]
    case Stripe.Charge.create(%{
      amount: amount,
      currency: "usd",
      source: token,
      description: "Example charge"
    }) do
      {:ok, charge} ->
        {:ok, _payment} =
          %Payment{}
          |> Payment.changeset(%{amount: amount, stripe_id: charge.id})
          |> YourApp.Repo.insert()
        conn
        |> put_flash(:info, "Payment successful.")
        |> redirect(to: ~p"/payment/thank-you?amount=#{amount}")
      {:error, error} ->
        conn
        |> put_flash(:error, "Payment failed: #{error.message}")
        |> render(:new, changeset: Payment.changeset(%Payment{}, payment_params))
    end
  end

  def thank_you(conn, %{"amount" => amount}) do
    render(conn, :thank_you, amount: amount)
  end
end
```

### 6. HTML Components

Create `lib/your_app_web/controllers/payment_html.ex`:

```elixir
defmodule YourAppWeb.PaymentHTML do
  use YourAppWeb, :html
  embed_templates "payment_html/*"

  attr :changeset, Ecto.Changeset, required: true
  attr :action, :string, required: true
  def payment_form(assigns) do
    ~H"""
    <div class="max-w-md mx-auto mt-8 p-6 bg-white rounded-lg shadow-md">
      <.form :let={f} for={@changeset} action={@action} class="space-y-6">
        <div>
          <.input field={f[:amount]} type="number" label="Amount (in cents)" class="mt-1 block w-full" />
        </div>
        <div>
          <label for="card-element" class="block text-sm font-medium text-gray-700">Credit or debit card</label>
          <div id="card-element" class="mt-1 block w-full">
            <!-- Stripe Elements will insert the card input here -->
          </div>
          <div id="card-errors" role="alert" class="mt-2 text-sm text-red-600"></div>
        </div>
        <input type="hidden" name={input_name(f, :token)} id="stripe_token" value={input_value(f, :token)} />
        <div>
          <.button type="submit" class="w-full">Pay Now</.button>
        </div>
      </.form>
    </div>
    """
  end

  attr :amount, :string, required: true
  def thank_you(assigns)
end
```

### 7. Templates

Create `lib/your_app_web/controllers/payment_html/new.html.heex`:

```heex
<h1 class="text-3xl font-bold text-center mt-8 mb-6">New Payment</h1>
<.payment_form changeset={@changeset} action={~p"/payment"} />

<script src="https://js.stripe.com/v3/"></script>
<script>
  var stripe = Stripe('<%= @stripe_publishable_key %>');
  var elements = stripe.elements();
  var style = {
    base: {
      fontSize: '16px',
      color: '#32325d',
      '::placeholder': {
        color: '#aab7c4'
      },
    },
    invalid: {
      color: '#fa755a',
      iconColor: '#fa755a'
    }
  };
  var card = elements.create('card', {style: style});
  card.mount('#card-element');

  card.addEventListener('change', function(event) {
    var displayError = document.getElementById('card-errors');
    if (event.error) {
      displayError.textContent = event.error.message;
    } else {
      displayError.textContent = '';
    }
  });

  var form = document.querySelector('form');
  form.addEventListener('submit', function(event) {
    event.preventDefault();

    stripe.createToken(card).then(function(result) {
      if (result.error) {
        var errorElement = document.getElementById('card-errors');
        errorElement.textContent = result.error.message;
      } else {
        var tokenInput = document.getElementById('stripe_token');
        tokenInput.value = result.token.id;
        form.submit();
      }
    });
  });
</script>
```

### 8. Wire up the router

In `lib/your_app_web/router.ex`:

```elixir

scope "/", YourAppWeb do
  pipe_through :browser

  # existing routes

  get "/payment/new", PaymentController, :new
  post "/payment", PaymentController, :create
  get "/payment/thank-you", PaymentController, :thank_you

end
```

## Stripity Stripe Integration

The `create` action in the `PaymentController` demonstrates the simplicity of using Stripity Stripe. The `Stripe.Charge.create/1` function encapsulates the complexities of creating a charge, including constructing headers, encoding the request body, and parsing the response.

## Conclusion

This guide demonstrates the basic implementation of Stripe payments in a Phoenix 1.7 application using Stripity Stripe. The new component-based structure in Phoenix 1.7 promotes modular code organization, although it requires some adjustment in development approach.

This implementation covers the fundamentals of payment processing. For more advanced features such as subscriptions or invoicing, refer to the Stripity Stripe documentation.
