import '../styles/globals.css'
import EditMapProvider from '../contexts/EditMapProvider'

function MyApp({ Component, pageProps }) {
  return (
    <EditMapProvider>
      <Component {...pageProps} />
    </EditMapProvider>
  )
}

export default MyApp
