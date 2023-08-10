import Questionnaire from '../components/Questionnaire';
import Navbar from '../components/Navbar';

  
const Challenge = () => {
    return (
        <div>
            <Navbar />
            <div className="centered-container">
                <h1>Challenge Form</h1>
                <Questionnaire />
            </div>

            <style jsx>{`
                .centered-container {
                    min-height: calc(100vh - [Height of Navbar]);
                    display: flex;
                    flex-direction: column;
                    justify-content: center;
                    align-items: center;
                }
            `}</style>
        </div>
    );
};
  
export default Challenge;
