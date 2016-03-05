---
layout: page
title: Posts by Categories
---
<ul>
{% for category in site.categories %}
  <li>{{ category | first }}
    <ul>
    {% for posts in category %}
      {% for post in posts %}
        {% if post.url %}
          <li><a href="{{ post.url }}">{{ post.title }}</a></li>
        {% endif %}
      {% endfor %}
    {% endfor %}
    </ul>
  </li>
{% endfor %}
</ul>
