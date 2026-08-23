import { useState } from 'react';
import { Link } from "react-router-dom";
import { isvalidemail } from '../utils/validation';

function Register()
{
	const [username, setUsername] = useState("");
	const [email, setEmail] = useState("");
	const [password, setPassword] = useState("");
	const [confirmPassword, setConfirmPassword] = useState("");
	const [error, setError] = useState("");

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
				<h1>Creer un compte</h1>
				{error && <p className='error'>{error}</p>}
				<input type="text" placeholder="Nom d'utilisateur" required value={username} onChange={(e) => setUsername(e.target.value)} />
				<input type="email" placeholder="Email" required value={email} onChange={(e) => setEmail(e.target.value)} />
				<input type="password" placeholder='Mot de passe' required value={password} onChange={(e) => setPassword(e.target.value)} />
				<input type="password" placeholder='Confirmer le mot de passe' required value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} />
				<button>Creer mon compte</button>
				<p><Link to="/login"> Retour</Link></p>
			</form>
		</div>
	);
}

export default Register;