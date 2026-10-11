const fetchUser = async (id) => {
    try {
        const res = await fetch(`/api/users/${id}`);
        return await res.json();
    } catch (err) {
        console.error(err);
    }
};
