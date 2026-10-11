function fetchUser(id) {
    return fetch('/api/users/' + id)
        .then(res => res.json())
        .catch(err => console.error(err));
}
