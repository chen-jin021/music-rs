document.addEventListener("DOMContentLoaded", function () {
	const exportBtn = document.getElementById("exportToTidal");

	if (exportBtn) {
		exportBtn.addEventListener("click", function () {
			fetch("/playlist/export")
				.then((response) => {
					if (response.ok) {
						return response.json();
					} else {
						throw new Error("Network Response Error");
					}
				})
				.then((data) => {
					// Open the TIDAL login URL in a new tab
					window.open(data.login_url, "_blank");

					// Start polling to check if authentication is complete
					const intervalId = setInterval(() => {
						fetch("/check_tidal_auth")
							.then((response) => response.json())
							.then((data) => {
								if (data.authenticated) {
									clearInterval(intervalId);
									window.location.href = "/tidal_callback"; // Redirect to the callback route
								}
							})
							.catch((error) => console.error("Error:", error));
					}, 3000); // Poll every 3 seconds, adjust as needed
				})
				.catch((error) => console.error("Error:", error));
		});
	}
});
