import { useState, useEffect } from "react";

export function useAuth ()
{
	const [isAuthen, setauthen] = useState(false);
	const [loading, setloading] = useState(true);

	useEffect(() =>
	{
		const token = localStorage.getItem("token");
		setauthen(!!token);
		setloading(false);
	}, []);

	function login(token)
	{
		localStorage.setItem("token", token);
		setauthen(true);
	}

	function logout()
	{
		localStorage.removeItem("token");
		setauthen(false);
	}

	return { isAuthen, loading, login, logout};
}