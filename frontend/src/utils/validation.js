export const PASSWORD_MIN_LENGTH = Number(import.meta.env.VITE_PASSWORD_MIN_LENGTH);
export const PASSWORD_MAX_LENGTH = Number(import.meta.env.VITE_PASSWORD_MAX_LENGTH);

export function isValidEmail(email)
{
	const adr = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;
	return adr.test(email);
}

export function isValidUsername(username)
{
	const pattern = /^[A-Za-z0-9._-]{3,50}$/;
	return pattern.test(username);
}

export function passwordLength(password)
{
	return [...password].length;
}

export function hasControlCharacters(value)
{
	return [...value].some((character) => {
		const code = character.codePointAt(0);
		return code < 0x20 || code === 0x7f;
	});
}

export function isValidPassword(password)
{
	const length = passwordLength(password);
	return length >= PASSWORD_MIN_LENGTH && length <= PASSWORD_MAX_LENGTH && !hasControlCharacters(password);
}

export function isValidIdentifier(identifier)
{
	return identifier.includes("@") ? isValidEmail(identifier) : isValidUsername(identifier);
}
