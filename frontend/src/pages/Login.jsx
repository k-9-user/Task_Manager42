import { useState } from 'react'
import "@fontsource/nabla";
import './login.css';
import { Link } from "react-router-dom";
import { useTranslation } from 'react-i18next';
import LanguageSwitcher from '../components/LanguageSwitcher';

function Login()
{
	const [email, setEmail] = useState("");
	const [password, setPassword] = useState("");
	const { t } = useTranslation();

	function handleSubmit(e) {
		e.preventDefault();
		console.log(`Utilisateur : ${email}`);
		console.log(`Mot de passe : ${password}`);
		// TODO: appel à authService.login(email, password)
	}
	return (
		<div className="login-page">
			<form className="login-box" onSubmit={handleSubmit}>
				<h1>Transcendance</h1>
				<LanguageSwitcher />
				<input type="text" placeholder={t("login.username")} value={email} onChange={(e) => setEmail(e.target.value)}
				/>
				<input type="password" placeholder={t("login.password")} value={password} onChange={(e) => setPassword(e.target.value)}
				/>
				<button>{t("login.submit")}</button>
				<p><Link to="/register">{t("login.register")}</Link></p>
			</form>
		</div>
	);
}

export default Login;