Jekyll::Hooks.register :site, :post_write do |site|
  # Only run during jekyll build, not jekyll serve
  if site.config['serving'] == true
    puts "⏭️  Skipping README generation during jekyll serve"
    next
  end
  
  latest_posts = site.posts.docs.reverse.first(5)

  readme_content = <<~README
    # Hey there 👋

    I'm Sid, a software engineer who writes about code, performance, and the occasional philosophical tangent.

    ## Latest Blog Posts

    #{latest_posts.map do |post|
      # Extract a brief excerpt for the description
      content = post.content.gsub(/<[^>]*>/, '').strip
      sentences = content.split(/[.!?]+/)
      first_sentence = sentences.first&.strip
      excerpt = if first_sentence && first_sentence.length > 50
        first_sentence + '.'
      else
        content[0..150].strip + '...'
      end

      "### [#{post.data['title']}](https://sngeth.github.io#{post.url})\n" \
      "*#{post.date.strftime('%B %d, %Y')}*\n\n" \
      "#{excerpt}\n"
    end.join("\n")}

    ---

    *More posts at [sngeth.github.io](https://sngeth.github.io)*
  README

  # Write to your profile repo
  profile_readme_path = File.expand_path('../sngeth/README.md', site.source)
  profile_repo_path = File.dirname(profile_readme_path)

  # Only write if the path exists (profile repo is cloned alongside blog repo)
  if File.exist?(profile_repo_path)
    File.write(profile_readme_path, readme_content)
    puts "✅ Profile README.md updated with latest blog posts"

    # Auto-commit and push the changes
    Dir.chdir(profile_repo_path) do
      system("git add README.md")
      if system("git diff --cached --quiet")
        puts "📝 No changes to commit"
      else
        commit_message = "Update README with latest blog posts"
        system("git commit -m \"#{commit_message}\"")
        system("git push origin main")
        puts "🚀 Changes committed and pushed to GitHub"
      end
    end
  else
    puts "⚠️  Profile repo not found at #{profile_repo_path}"
  end
end
