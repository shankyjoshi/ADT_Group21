function fetchCategoryProducts() {
    var category = document.getElementById('category-select').value;
    var categoryTitleDiv = document.getElementById('category-title');
    if (category) {
        // Make an AJAX request to the Flask route
        fetch('/category_products/' + encodeURIComponent(category))
            .then(response => response.text())
            .then(html => {
                // Inject the HTML into the category products section
                document.getElementById('category-products').innerHTML = html;
                // Update the category title
                if (categoryTitleDiv) {
                    categoryTitleDiv.innerText = `Top 5 Products in ${category.replace(/&/g, ' and ')} Category`;
                }
            })
            .catch(error => console.error('Error fetching category products:', error));
    } else {
        // Clear the category products section if no category is selected
        document.getElementById('category-products').innerHTML = '';
        if (categoryTitleDiv) {
            categoryTitleDiv.innerText = 'Top 5 Products in Category';
        }
    }
}

document.addEventListener('DOMContentLoaded', (event) => {
    document.getElementById('logoutButton').addEventListener('click', function() {
        window.location.href = '/logout'; // Use the URL that is bound to your logout function
    });
});


