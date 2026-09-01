import { useState } from 'react';
import './register.css';
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
				setError(t("register.username"));
			else if (!email.trim())
				setError(t("register.email"));
			else if (!password)
				setError(t("register.password"));
			else
				setError(t("register.cpassword"));
			return ;
		}
		if (!isvalidemail(email))
		{
			setError(t("register.invaemail"));
			return ;
		}
		if (password !== confirmPassword)
		{
			setError(t("register.falsepassword"));
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
				<p></p>
				<input type="email" placeholder="Email" required value={email} onChange={(e) => setEmail(e.target.value)} />
				<p></p>
				<input type="password" placeholder={t("login.password")} required value={password} onChange={(e) => setPassword(e.target.value)} />
				<p></p>
				<input type="password" placeholder={t("register.confirmpassword")} required value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} />
				<p></p>
				<button>{t("register.createcount")}</button>
				<p><Link to="/login">{t("register.return")}</Link></p>
			</form>
		</div>
	);
}

export default Register;