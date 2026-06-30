import { Navigate } from 'react-router';

export function NotFoundRedirect() {
  return <Navigate to="/" replace />;
}
