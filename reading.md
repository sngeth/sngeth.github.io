---
layout: page
title: Reading
---

Things I'm reading from around the web on AI, programming, philosophy, and strength sports.

<div class="reading-list">
  {% assign categories = "ai,programming,philosophy,strength" | split: "," %}
  {% assign category_labels = "AI,Programming,Philosophy,Strength Sports" | split: "," %}

  {% for cat in categories %}
    {% assign idx = forloop.index0 %}
    <h2>{{ category_labels[idx] }}</h2>
    <ul class="reading-items">
      {% for item in site.data.reading_list %}
        {% if item.category == cat %}
        <li class="reading-item">
          <a href="{{ item.url }}" target="_blank" rel="noopener">{{ item.title }}</a>
          <span class="reading-meta">{{ item.source }}{% if item.date %} &middot; {{ item.date }}{% endif %}</span>
        </li>
        {% endif %}
      {% endfor %}
    </ul>
  {% endfor %}
</div>
