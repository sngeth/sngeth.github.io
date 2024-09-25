---
layout: post
title: "Enhancing Your Codebase with Commitizen"
category: "Git"
comments: true
---
One often overlooked aspect of a code base is the commit history.
Enter Commitizen, a powerful tool that standardizes commit messages and automates changelog generation.
In this post, we'll explore how Commitizen can improve your development workflow and discuss some common commit guidelines.

## What is Commitizen?

Commitizen is a command-line utility that helps developers write standardized commit messages. It provides an interactive prompt that guides you through the commit process, ensuring that your commits follow a consistent format.

## Installing and Configuring Commitizen

### Installation

You can install Commitizen globally using either npm or yarn:

Using npm:
```bash
npm install -g commitizen
```

Using yarn:
```bash
yarn global add commitizen
```

### Configuration

To customize Commitizen for your project, you can create a `.czrc` file in your project root or home directory. Here's an example of a `.czrc` file:

```json
{
  "path": "cz-conventional-changelog",
  "types": {
    "feat": {
      "description": "A new feature"
    },
    "fix": {
      "description": "A bug fix"
    },
    "docs": {
      "description": "Documentation only changes"
    },
    "style": {
      "description": "Changes that do not affect the meaning of the code"
    },
    "refactor": {
      "description": "A code change that neither fixes a bug nor adds a feature"
    },
    "perf": {
      "description": "A code change that improves performance"
    },
    "test": {
      "description": "Adding missing tests"
    },
    "chore": {
      "description": "Changes to the build process or auxiliary tools"
    },
    "a11y": {
      "description": "Adding accessibility features"
    },
    "sec": {
      "description": "A code change related to security"
    },
    "devops": {
      "description": "A code change related to devops"
    }
  },
  "messages": {
    "type": "Select the type of change you're committing:",
    "subject": "Write a short, imperative tense description of the change:\n",
    "body": "Provide a longer description of the change (optional). Use Markdown for formatting:\n",
    "breaking": "List any breaking changes:\n",
    "footer": "List any issues closed by this change (optional):\n"
  },
  "subjectLimit": 100,
  "upperCaseSubject": false,
  "allowCustomScopes": false,
  "allowBreakingChanges": ["feat", "fix"],
  "footerPrefix": "ISSUES CLOSED:"
}
```

This configuration file allows you to customize the commit types, prompts, and other aspects of Commitizen's behavior. You can adjust these settings to match your project's specific needs.

For more detailed information on configuration options, you can refer to the [Commitizen GitHub documentation](https://github.com/commitizen/cz-cli).

## Benefits of Using Commitizen

1. **Consistency**: Enforces a uniform commit message format across your team.
2. **Clarity**: Makes it easier to understand the purpose of each commit at a glance.
3. **Automation**: Facilitates automatic generation of changelogs.
4. **Better Code Reviews**: Standardized commits make it easier to review code changes.

## Common Commit Types

Let's break down some commonly used commit types and their purposes:

- **feat**: A new feature
- **fix**: A bug fix
- **docs**: Documentation only changes
- **style**: Changes that do not affect the meaning of the code (e.g., formatting)
- **refactor**: A code change that neither fixes a bug nor adds a feature
- **perf**: A code change that improves performance
- **test**: Adding missing tests
- **chore**: Changes to the build process or auxiliary tools
- **a11y**: Adding accessibility features
- **sec**: A code change related to security
- **devops**: A code change related to DevOps

## Anatomy of a Good Commit Message

A well-structured commit message typically includes:

1. **Type**: The category of the change (e.g., feat, fix, docs)
2. **Subject**: A short, imperative description of the change
3. **Body** (optional): A longer description of the change, using Markdown for formatting
4. **Breaking Changes** (if any): List of any breaking changes introduced
5. **Footer** (optional): References to issues closed by the change

## Using Commitizen: A Walkthrough

Let's walk through the process of creating a commit using Commitizen. After you've made your changes and staged them with `git add`, instead of using `git commit`, you'll use `git cz`. Here's what the process looks like:

1. In your terminal, type:
   ```
   git cz
   ```

2. Commitizen will launch and guide you through the commit process:

   ```
   ? Select the type of change you're committing: (Use arrow keys)
   ❯ feat:     A new feature
     fix:      A bug fix
     docs:     Documentation only changes
     style:    Changes that do not affect the meaning of the code
     refactor: A code change that neither fixes a bug nor adds a feature
     perf:     A code change that improves performance
     test:     Adding missing tests
   (Move up and down to reveal more choices)
   ```

   Use the arrow keys to select the appropriate type and press Enter.

3. Next, you'll be prompted to enter the scope of the change (optional):

   ```
   ? What is the scope of this change (e.g. component or file name): (press enter to skip)
   auth
   ```

   Enter the scope or press Enter to skip.

4. Now, enter a short description of the change:

   ```
   ? Write a short, imperative tense description of the change:
   implement JWT-based user authentication
   ```

5. Provide a longer description if needed:

   ```
   ? Provide a longer description of the change: (press enter to skip)
   Implement JWT-based authentication for user login and registration.
   This includes:
   - Creating login and registration endpoints
   - Implementing password hashing
   - Setting up JWT token generation and validation
   ```

6. Indicate if there are any breaking changes:

   ```
   ? Are there any breaking changes? (y/N)
   y
   ```

   If you answer yes, you'll be prompted to describe the breaking changes:

   ```
   ? Describe the breaking changes:
   API now requires authentication for most endpoints
   ```

7. Finally, indicate if this change affects any open issues:

   ```
   ? Does this change affect any open issues?
   y
   ```

   If yes, you'll be prompted to add issue references:

   ```
   ? Add issue references (e.g. "fix #123", "re #123".):
   Closes #123, #124
   ```

8. Commitizen will then generate the commit message based on your inputs and create the commit:

   ```
   [master 5c25de1] feat(auth): implement JWT-based user authentication

   Implement JWT-based authentication for user login and registration.
   This includes:
   - Creating login and registration endpoints
   - Implementing password hashing
   - Setting up JWT token generation and validation

   BREAKING CHANGE: API now requires authentication for most endpoints

   Closes #123, #124
   ```

This process ensures that your commit message is structured consistently and contains all the necessary information. The resulting commit message will look like this:

```
feat(auth): implement JWT-based user authentication

Implement JWT-based authentication for user login and registration.
This includes:
- Creating login and registration endpoints
- Implementing password hashing
- Setting up JWT token generation and validation

BREAKING CHANGE: API now requires authentication for most endpoints

Closes #123, #124
```

By following this process, you create commits that are not only informative but also adhere to a consistent format, making it easier for your team to understand changes and automatically generate meaningful changelogs.

## Sample Problematic Commit

While Commitizen won't automatically reject commits, it guides users towards more descriptive messages. Here's an example of a commit that Commitizen would try to improve:

```
type: updated stuff

Select the type of change you're committing:
> feat
Write a short, imperative tense description of the change:
> updated stuff
Provide a longer description of the change (optional). Use Markdown for formatting:
>
List any breaking changes:
>
List any issues closed by this change (optional):
>
```

In this scenario, Commitizen would create a commit message like:

```
feat: updated stuff
```

While this commit would be accepted, it still lacks specificity and doesn't provide useful information about the changes made. Commitizen's prompts encourage developers to provide more details, but it ultimately depends on the user to input meaningful information.

## Generating and Understanding Changelogs

While Commitizen helps in creating structured commit messages, generating changelogs requires additional tools that work well with Commitizen's commit format. Let's explore how to generate a changelog and what the result looks like.

### Generating a Changelog

Two popular options for generating changelogs are `standard-version` and `conventional-changelog-cli`.

#### Using standard-version

1. Install `standard-version`:

   ```bash
   npm install -g standard-version
   ```

2. Generate a changelog:

   ```bash
   standard-version
   ```

   This command analyzes your commits, updates your version in package.json, generates a changelog, creates a new commit with these changes, and creates a new tag with the new version number.

3. To generate the changelog without bumping the version:

   ```bash
   standard-version --skip.bump --skip.tag
   ```

#### Using conventional-changelog-cli

1. Install `conventional-changelog-cli`:

   ```bash
   npm install -g conventional-changelog-cli
   ```

2. Generate the changelog:

   ```bash
   conventional-changelog -p angular -i CHANGELOG.md -s
   ```

3. To generate the entire changelog from scratch:

   ```bash
   conventional-changelog -p angular -i CHANGELOG.md -s -r 0
   ```

### Automating Changelog Generation

Add this script to your `package.json` to automate changelog generation:

```json
{
  "scripts": {
    "version": "conventional-changelog -p angular -i CHANGELOG.md -s && git add CHANGELOG.md"
  }
}
```

Now, running `npm version` will automatically update your changelog.

### Example Changelog

Here's an example of what a generated changelog might look like when following Commitizen conventions:

```markdown
# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.2.0] - 2024-09-20

### Added
- feat: implement user authentication system (#123)
  - Added JWT-based authentication for login and registration
  - Created new endpoints for user management
- feat: add dark mode to user interface (#145)
- feat(api): introduce rate limiting for public endpoints (#150)

### Changed
- refactor: optimize database queries for better performance (#135)
- style: update color scheme across the application (#140)

### Fixed
- fix: resolve issue with password reset functionality (#128)
- fix(ui): correct alignment of buttons in mobile view (#142)

### Security
- sec: update dependencies to address known vulnerabilities (#155)

## [1.1.0] - 2024-08-15

### Added
- feat: introduce search functionality for products (#110)
- feat(api): add pagination to list endpoints (#115)

### Changed
- refactor: restructure folder organization for better modularity (#105)
- perf: optimize image loading for faster page renders (#120)

### Fixed
- fix: resolve cart calculation errors (#112)
- fix(ui): correct responsive layout issues on tablet devices (#118)

### Documentation
- docs: update API documentation with new endpoints (#125)

## [1.0.1] - 2024-07-30

### Fixed
- fix: resolve critical bug in payment processing (#102)
- fix(ui): correct typos in error messages (#104)

### Security
- sec: implement additional checks for user input sanitization (#103)

## [1.0.0] - 2024-07-15

### Added
- Initial release of the application
- feat: core e-commerce functionality including product listing, cart, and checkout
- feat: user registration and profile management
- feat: basic reporting and analytics for administrators

### Documentation
- docs: create initial README and contribution guidelines (#95)
- docs: add inline code comments for complex functions (#97)

### DevOps
- devops: set up CI/CD pipeline for automated testing and deployment (#90)
```

This changelog demonstrates how structured commit messages translate into a clear, informative record of project changes. It's organized by version, with changes categorized based on their type. Each entry corresponds directly to a commit, making it easy to trace changes back to their source.

The effectiveness of these changelog generation tools depends on the quality and consistency of your commit messages. This is where Commitizen really shines, ensuring that all your commits follow a format that these changelog generators can understand and process.
## Conclusion

By adopting Commitizen and following consistent commit guidelines, you can significantly improve your codebase's maintainability and documentation. While Commitizen provides a framework for better commits, it's up to the development team to ensure that the content of the commits is meaningful and descriptive.

Remember, good commit messages are a form of documentation. They not only help your team understand changes but also make it easier for future developers (including yourself) to understand the project's history and evolution. The more specific and descriptive your commit messages are, the more valuable they become in the long run, especially when it comes to generating comprehensive and useful changelogs.
