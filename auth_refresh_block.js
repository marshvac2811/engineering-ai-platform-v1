async function refreshAccessToken() {
    const refreshToken = localStorage.getItem("engineering_ai_refresh_token");

    if (!refreshToken) {
        throw new Error("No refresh token available. Please sign in again.");
    }

    const response = await fetch(
        "https://vaxerlbgwwlfamncevdg.supabase.co/auth/v1/token?grant_type=refresh_token",
        {
            method: "POST",
            headers: {
                "apikey": "sb_publishable_X68FRNA50gzwKqH7SFbOGQ_OyemX0_s",
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                refresh_token: refreshToken
            })
        }
    );

    const data = await response.json();

    if (!response.ok || !data.access_token) {
        localStorage.removeItem("engineering_ai_access_token");
        localStorage.removeItem("engineering_ai_refresh_token");
        throw new Error(data.error_description || data.msg || "Session refresh failed. Please sign in again.");
    }

    localStorage.setItem("engineering_ai_access_token", data.access_token);

    if (data.refresh_token) {
        localStorage.setItem("engineering_ai_refresh_token", data.refresh_token);
    }

    return data.access_token;
}

async function authFetch(url, options = {}) {
    const requestOptions = Object.assign({}, options);
    const headers = Object.assign({}, requestOptions.headers || {});

    let accessToken = localStorage.getItem("engineering_ai_access_token");

    if (!accessToken) {
        throw new Error("No active authentication session. Please sign in.");
    }

    headers["Authorization"] = "Bearer " + accessToken;
    requestOptions.headers = headers;

    let response = await fetch(url, requestOptions);

    if (response.status !== 401) {
        return response;
    }

    accessToken = await refreshAccessToken();

    const retryHeaders = Object.assign({}, headers, {
        "Authorization": "Bearer " + accessToken
    });

    requestOptions.headers = retryHeaders;

    return fetch(url, requestOptions);
}
