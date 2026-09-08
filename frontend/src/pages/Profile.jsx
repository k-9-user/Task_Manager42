import { useState, useEffect } from "react";
import { apiFetch } from "../services/api";
import { useTranslation } from "react-i18next";


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
	const { t } = useTranslation();

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

	if(loading)
		return <p>{t("loading.load")}</p>;
	if (error)
		return <p className="error">{t("error.err")} : {error}</p>;

	return (
		<div className="profile-page">
			<h1>{t("random.myprofile")}</h1>
			<p>{t("login.username")} : {user.username} </p>
			<p>Email : {user.email}</p>
			<img src={user.avatar_url} alt="avatar" />
		</div>
	);
}

export default Profile;