# User Guide

## Introduction
Welcome to Project Sophia! This guide will walk you through the process of using the application to manage your code snippets, solve programming problems, and leverage AI for code generation.

## Account Setup

### Registration
1.  Navigate to the **Register** page.
2.  Enter a unique **Username**, your **Email**, and a **Password**.
3.  Confirm your password in the **Repeat Password** field.
4.  Click the **Register** button.

### Login
1.  Navigate to the **Login** page.
2.  Enter your **Username** and **Password**.
3.  (Optional) Check **Remember Me** to stay logged in.
4.  Click the **Sign In** button.

### Profile Management
1.  Click on your username or profile icon to go to your **User Profile**.
2.  Click **Edit Profile** to change your username, email, or avatar.
3.  To change your password, enter your **Current Password**, then your **New Password** and **Repeat New Password**.
    > **Note:** A strong password should be at least 8 characters long and include lowercase, uppercase, digits, and symbols.
4.  Click **Save Changes** to update your profile.

## Core Workflows

### Creating a New Code Snippet
1.  Navigate to the **Create Snippet** page.
2.  Enter a **Title** for your snippet.
3.  Select a **Collection** (optional) to organize your snippet.
4.  Choose the appropriate **Language** for syntax highlighting.
5.  Add a **Description** (optional) to explain your code.
6.  Paste your **Code** into the provided text area.
7.  Add **Tags** (comma-separated) for easier searching.
8.  Click **Save Snippet**.

### Managing Collections
1.  Go to the **Collections** page.
2.  **Create New Collection:**
    1.  Enter a **Collection Name**.
    2.  Select a **Parent Collection** (optional) to create nested collections.
    3.  Click **Create Collection**.
3.  **View Collection:** Click on a collection's name to view its contents.
4.  **Rename Collection:** Click the **Rename** button next to a collection.
5.  **Delete Collection:** Click the **Delete** button.
    > **Warning:** Deleting a collection will *not* delete the snippets within it; they will become uncollected.
6.  **Reorder Collections:** Use the **up** and **down** arrow buttons to change the display order of collections.

### Adding a LeetCode Problem
1.  Navigate to the **Add Problem** page.
2.  Enter the **Problem Title** and **Problem Description**.
3.  Select the **Difficulty** (Easy, Medium, Hard).
4.  Add **Tags** (comma-separated) for the problem.
5.  (Optional) Provide the **LeetCode URL** if it's an external problem.
6.  Click **Add Problem**.

### Generating and Approving Solutions
1.  Go to the **Generate Solution** page.
2.  Select a **Problem** from the dropdown.
3.  Choose the **Solution Language**.
4.  Click **Generate Solution**. The AI will attempt to generate a solution.
5.  After the solution is generated, you can **Approve Solution** if it meets the requirements. Approved solutions are stored.

### AI Code Formatting
1.  When viewing or editing a code snippet, locate the "Format Code with AI" button.
2.  Clicking this button will send the code to the AI service for formatting.
3.  The formatted code will replace the original content in the editor. Review the changes and save the snippet.

### AI-Powered Code Explanation and Tagging
1.  When viewing a code snippet, you can find options to "Explain Code with AI" or "Suggest Tags with AI".
2.  Clicking "Explain Code" will generate a detailed, structured explanation of the snippet's logic, intent, and complexity.
3.  Clicking "Suggest Tags" will provide a comma-separated list of relevant tags to help categorize your snippet.

## Advanced Features

### Bulk Actions
1.  On pages displaying multiple snippets, select snippets using checkboxes.
2.  Use the **Bulk Actions** dropdown to choose **Delete**, **Copy**, or **Move**.
3.  For **Copy** or **Move**, select a **Target Collection**.
4.  Click **Perform Bulk Action**.

## FAQ
- **How do I search for snippets?** Use the search bar in the navigation.
- **Can I add my own languages?** Currently, the supported languages are fixed.
- **What happens if AI generation or formatting fails?** The system will provide an error message. You can try refining your prompt, re-generating, or formatting again.
- **What is AI code formatting?** It's a feature that uses artificial intelligence to automatically reformat your code to improve readability and consistency, applying standard indentation, spacing, and style.
