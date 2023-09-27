import '../styles/globals.css'
import EditMapProvider from '../contexts/EditMapProvider'
import MbtilesProvider from '../contexts/MbtilesProvider'

function MyApp({ Component, pageProps }) {
  return (
    <EditMapProvider>
      <MbtilesProvider>
      <Component {...pageProps} />
      </MbtilesProvider>
    </EditMapProvider>
  )
}

export default MyApp
