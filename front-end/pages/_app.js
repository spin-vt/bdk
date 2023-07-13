import '../styles/globals.css'
import MbtilesProvider from '../components/MbtilesProvider';
import SelectedLocationProvider from '../components/SelectLocationProvider';

function MyApp({ Component, pageProps }) {
  return (
    <MbtilesProvider>
      <SelectedLocationProvider>
        <Component {...pageProps} />
      </SelectedLocationProvider>
    </MbtilesProvider>
  )
}

export default MyApp
