import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';

import App from './App.jsx';
import Gate from './components/Gate.jsx';
import { LanguageProvider } from './lib/i18n.jsx';
import './styles/tokens.css';
import './styles/components.css';
import './styles/dock.css';
import './styles/assistant.css';
import './styles/app.css';

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <LanguageProvider>
      {/* Outside the router: the sign-in form is not a route, and a signed-out
          viewer should get it whatever address they arrived at. */}
      <Gate>
        <BrowserRouter>
          <App />
        </BrowserRouter>
      </Gate>
    </LanguageProvider>
  </StrictMode>,
);
