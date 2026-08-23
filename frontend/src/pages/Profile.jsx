import { useState, useEffect } from "react";
import { apiFetch } from "../services/api";


const USE_MOCK = true; // a retirer

const mockUser = {
  username: "Pingouin",
  email: "tintin@test.com",
  avatar_url: "https://api.dicebear.com/10.x/bottts/svg",
};

function Profile() {
	const [user, setUser] = useState(null);
	const [error, setError] = useState("");
	const [loading, setLoading] = useState(true);

	useEffect(() => {
	  async function fetchProfile() {
	    try {
        if (USE_MOCK) {
          setUser(mockUser);
        } else {
          const data = await apiFetch("/api/users/me");
          setUser(data.user);
        }
	    } catch (err) {
	      setError(err.message);
	    } finally {
	      setLoading(false);
	    }
	  }

	fetchProfile();
	}, []);

	if(loading) return <p>Chargement...</p>;
	if (error) return <p className="error">Erreur : {error}</p>;

	return (
		<div className="profile-page">
			<h1>Mon profil</h1>
			<p>Nom d'utilsateur : {user.username} </p>
			<p>Email : {user.email}</p>
			<img src={user.avatar_url} alt="avatar" />
		</div>
	);
}

export default Profile;