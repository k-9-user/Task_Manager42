import { useState } from 'react';
import { Link } from "react-router-dom";
import { isvalidemail } from '../utils/validation';
import { useTranslation } from 'react-i18next';
import LanguageSwitcher from '../components/LanguageSwitcher';

function Register()
{
	const [username, setUsername] = useState("");
	const [email, setEmail] = useState("");
	const [password, setPassword] = useState("");
	const [confirmPassword, setConfirmPassword] = useState("");
	const [error, setError] = useState("");
	const { t } = useTranslation();

	function handleSubmit (e) {
		e.preventDefault();
		if (!username.trim() || !email.trim() || !password || !confirmPassword)
		{
			if (!username.trim())
				setError("Veuillez entrer un nom d'utilisateur");
			else if (!email.trim())
				setError("Veuillez entrer une adresse mail");
			else if (!password)
				setError("Veuillez entrer un mot de passe");
			else
				setError("Veuillez confirmer votre mot de passe");
			return ;
		}
		if (!isvalidemail(email))
		{
			setError("Adresse email invalide");
			return ;
		}
		if (password !== confirmPassword)
		{
			setError("Les mots de passe ne correspondent pas");
			return ;
		}
		setError("");
		console.log(`Nouveau compte : ${username}, ${email}`);
	}
	return (
		<div className='register-page'>
			<form className='register-box' onSubmit={handleSubmit}>
				<h1>{t("login.register")}</h1>
				{error && <p className='error'>{error}</p>}
				<input type="text" placeholder={t("login.username")} required value={username} onChange={(e) => setUsername(e.target.value)} />
				<input type="email" placeholder="Email" required value={email} onChange={(e) => setEmail(e.target.value)} />
				<input type="password" placeholder={t("login.password")} required value={password} onChange={(e) => setPassword(e.target.value)} />
				<input type="password" placeholder={t("register.confirmpassword")} required value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} />
				<button>{t("register.createcount")}</button>
				<p><Link to="/login">{t("register.return")}</Link></p>
			</form>
		</div>
	);
}

export default Register;