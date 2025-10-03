---
layout: post
title: tracking your wins with git
category: "Git"
date: 2025-09-22
pinned: true
---

another year down, and i'm trying to remember what i actually built this year. honestly? it's all a blur.

you know the feeling. you've been shipping code consistently, fixing bugs, building features, but when someone asks "what did you accomplish this year?" your brain just goes blank. was that auth refactor in march or july? did i ship the analytics dashboard before or after the mobile redesign?

## the problem with developer memory

we're constantly context switching. one day you're debugging a race condition in the payment flow, the next you're building a new onboarding experience, then suddenly you're optimizing database queries because the dashboard is slow. each task feels important in the moment, but they all blend together over months.

whether it's performance reviews, job interviews, or just internal reflection, people want concrete examples of your impact. "tell us about a complex technical challenge you solved" or "describe how you improved system performance." but when everything feels like just another tuesday, it's hard to remember which wins were actually significant.

## your git history is your accomplishment log

every commit you make is a timestamp of progress. your git history contains:

- exact dates of when you shipped features
- the complexity and scope of changes
- how many bugs you fixed vs features you built
- patterns in your work (are you always fixing the same types of issues?)
- collaboration evidence (co-authored commits, code reviews)

the trick is turning that raw commit data into a coherent story of growth and impact.

## the magic command

here's what i fed into an LLM to generate my yearly summary:

```bash
# get a year's worth of commits with stats
git log --author="your-email@company.com" \
        --since="2024-01-01" \
        --until="2024-12-31" \
        --pretty=format:"%h|%ad|%s" \
        --date=short \
        --all | head -50
```

then prompt your favorite LLM with:

> "analyze these git commits and create a technical accomplishments summary. group by major themes like features, bug fixes, performance improvements, and security. highlight the business impact and technical complexity. include specific metrics where possible."

## automating with a script

i've been using this technique for weekly standups too. here's a script that automates the whole process:

```bash
#!/bin/bash
# git-standup.sh - Generate AI-powered standup reports from git commits

set -e

DAYS=${1:-7}  # Default to last 7 days
AUTHOR=${2:-$(git config user.email)}
ENV_FILE=${3:-~/.env}

# Source environment variables
source "$ENV_FILE"

# Get git commits
COMMITS=$(git log --author="$AUTHOR" \
    --since="$DAYS days ago" \
    --pretty=format:"%h|%ad|%s" \
    --date=short \
    --all \
    --no-merges | head -50)

# Prepare the prompt
PROMPT="Analyze these git commits and create a concise standup update. Focus on:
- What was accomplished (group similar work)
- Any blockers or challenges implied by the commits
- Key technical wins or improvements
- Format as: Completed, In Progress, Blockers, Notes

Commits (format: hash|date|message):
$COMMITS"

# Use OpenAI API
if [[ -n "$OPENAI_API_KEY" ]]; then
    ESCAPED_PROMPT=$(echo "$PROMPT" | jq -Rs .)

    curl -s https://api.openai.com/v1/chat/completions \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $OPENAI_API_KEY" \
        -d "{
            \"model\": \"gpt-4o-mini\",
            \"messages\": [{
                \"role\": \"user\",
                \"content\": $ESCAPED_PROMPT
            }],
            \"max_tokens\": 1000
        }" | jq -r '.choices[0].message.content'
fi
```

just add your `OPENAI_API_KEY` to `~/.env` and run:

```bash
./git-standup.sh           # last 7 days
./git-standup.sh 3         # last 3 days
./git-standup.sh 14 your.email@company.com  # custom timeframe/author
```

## what the analysis revealed

looking at my own year through this lens was... honestly pretty shocking. here's what git actually tracked:

**major feature developments:**

1. webinar platform (2025)
- enhanced VCF platform to support webinars including:
  - post-registration functionality and user workflows
  - custom marketing capabilities for webinar events
  - early start/late end time configuration system
  - private webinar filtering for staff interfaces
- technical impact: enabled virtual employment workshops, expanding platform capabilities beyond traditional job fairs

2. virtual career fair (VCF) enhancements
- developed VCF featured jobs system - complete job highlighting and promotion feature
- built pre-event search functionality - allowing candidates to discover opportunities before events
- enhanced chat welcome message formatting with WYSIWYG input
- improved message template positioning and dropdown functionality
- created mobile-responsive interfaces for exhibitor lists and candidate interactions

3. event management & analytics
- built sold-out event handling system with automatic waitlist functionality
- created comprehensive messaging analytics with campaign details and performance tracking
- enhanced control center real-time statistics display

**security & performance contributions:**

security hardening
- strengthened password requirements and implemented secure reset flows
- prevented user enumeration attacks in authentication systems
- replaced insecure staff password generation with secure reset links
- added CSRF protection and input sanitization improvements

performance optimization
- resolved N+1 query issues in candidate searches and exhibitor displays
- optimized database queries and added proper indexing
- implemented efficient search filtering with elasticsearch integration
- added query optimization for large dataset operations

**technical problem solving:**

mobile & responsive design
- fixed critical mobile responsiveness issues across VCF interfaces
- resolved viewport and layout problems for exhibitor schedules
- implemented x-teleport solutions for dropdown menu clipping issues
- enhanced mobile chat functionality with proper input visibility

data export & reporting
- built comprehensive CSV export systems for:
  - staff organization users
  - client job postings with missing columns
  - candidate applications with enhanced filtering
  - event folder candidate downloads with rep attendance data

UI/UX improvements
- implemented advanced filtering systems with sidebar interfaces
- created sortable lists for completed one-on-one meetings

**business impact contributions:**

event operations
- enhanced attendee tracking with view confirmation systems
- implemented booth management with presence and broadcasting fixes
- created candidate folder filtering for improved exhibitor experience
- built time zone handling for multi-region events

client tools
- developed job deletion workflows with automatic credit refunds
- enhanced job application search with advanced filtering options
- created messaging template systems with positioning improvements
- implemented draft job management capabilities

quality assurance & testing
- fixed flaky test issues with proper mocking and stubbing
- implemented integration specs for complex workflows
- added test helpers for consistent testing patterns

**recent high-impact work (2024-2025):**
- september 2025: sold-out event handling and waitlist system
- august 2025: VCF enhancements and messaging analytics
- july 2025: staff candidate tracking and view confirmation
- june 2025: security hardening and password requirements

**technical skills demonstrated:**
- full-stack ruby on rails development
- javascript/stimulus frontend frameworks
- elasticsearch implementation and optimization
- database design and query optimization
- real-time features with turbo streams
- mobile-responsive design patterns
- security best practices implementation

## beyond the basic stats

the real value isn't just counting commits. it's seeing patterns:

**what types of problems do you gravitate toward?** my commits showed i spend a lot of time on integration challenges, mobile responsiveness, and real-time features.

**when are you most productive?** my commit timestamps revealed patterns i never noticed. heavy feature work in morning sprints, bug fixes and optimization in the afternoon.

**what's your technical growth path?** the progression from simple bug fixes early in the year to building complete subsystems later shows clear skill development. commits touching multiple systems prove comfort with complex, cross-cutting changes.

## staying on top of it

keep a running note of the big wins as they happen. git gives you the data, but you need to capture the context: why was this hard? what would've happened if you didn't fix it? how many users did this impact?

your commits are proof you've been busy. turning them into a story of impact? that's the difference between "i wrote code" and "i moved the business forward."
