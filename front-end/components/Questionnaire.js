import React, { useState } from "react";
import Button from "@mui/material/Button";
import { data } from "@maptiler/sdk";

const Questionnaire = () => {
  const questions = [
    "Contact Name",
    "Contact Email",
    "Contact Phone",
    "Category Code",
    "Location ID",
    "Address Primary",
    "City",
    "State",
    "Zip Code",
    "Zip Code Suffix",
    "Unit Count",
    "Building Type",
    "Non-bsl Code",
    "BSL lacks address flag",
    "Latitude",
    "Longitude",
    "Address ID",
  ];

  const [currentQuestionIndex, setCurrentQuestionIndex] = useState(0);
  const [answers, setAnswers] = useState(Array(questions.length).fill(null));

  const handleAnswer = (event) => {
    const updatedAnswers = [...answers];
    updatedAnswers[currentQuestionIndex] = event.target.value;
    setAnswers(updatedAnswers);
  };

  const handleBack = () => {
    if (currentQuestionIndex > 0) {
      setCurrentQuestionIndex(currentQuestionIndex - 1);
    }
  };

  const handleNext = () => {
    if (currentQuestionIndex < questions.length - 1) {
      setCurrentQuestionIndex(currentQuestionIndex + 1);
    }
  };

  const answeredCount = answers.filter((answer) => answer !== null).length;
  const allQuestionsAnswered = answeredCount === questions.length;

  const handleClear = () => {
    setCurrentQuestionIndex(0);
    setAnswers(Array(questions.length).fill(null));
  };

  function addToDatabase(event) {
    event.preventDefault();
    console.log("Adding to database...");
    const dataToSend = {
      contact_name: answers[0],
      contact_email: answers[1],
      contact_phone: answers[2],
      category_code: answers[3],
      location_id: answers[4],
      address_primary: answers[5],
      city: answers[6],
      state: answers[7],
      zip_code: answers[8],
      zip_code_suffix: answers[9],
      unit_count: answers[10],
      building_type: answers[11],
      non_bsl_code: answers[12],
      bsl_lacks_address_flag: answers[13],
      latitude: answers[14],
      longitude: answers[15],
      address_id: answers[16],
    };
    console.log(dataToSend)

    fetch("http://localhost:5000/submit-challenge", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(dataToSend),
    })
      .then((response) => response.json())
      .then((data) => {
        console.log(data);
      })
      .catch((error) => {
        console.error("Error:", error);
      });
  }

  return (
    <div className="super-container">
      <div className="container">
        <div className="accordion">
          <div className="status-bar">
            Answered: {answeredCount}/{questions.length} - Remaining:{" "}
            {questions.length - answeredCount}
          </div>

          <div className="accordion-item">
            <div className="accordion-header">
              {questions[currentQuestionIndex]}
            </div>
            <div className="accordion-content">
              <input
                type="text"
                value={answers[currentQuestionIndex] || ""}
                onChange={handleAnswer}
                placeholder="Enter your answer"
              />
            </div>
          </div>

          {currentQuestionIndex > 0 && (
            <button style={{ marginRight: "10px" }} onClick={handleBack}>
              Previous Question
            </button>
          )}
          {currentQuestionIndex < questions.length - 1 && (
            <button style={{ marginRight: "10px" }} onClick={handleNext}>
              Next
            </button>
          )}

          <button onClick={handleClear}>Clear All</button>
        </div>
      </div>

      {allQuestionsAnswered && (
        <Button
          variant="contained"
          color="secondary"
          style={{
            marginTop: "20px",
            marginLeft: "12vw",
            fontSize: "20px",
            padding: "12px 24px",
            minWidth: "150px",
          }}
          onClick={addToDatabase}
        >
          Submit
        </Button>
      )}

      <style jsx>{`
        .container {
          width: 500px;
          height: 300px;
          overflow-y: auto;
          padding: 15px;
          border: 1px solid #e1e1e1;
          box-shadow: 0px 4px 12px rgba(0, 0, 0, 0.1);
          border-radius: 8px;
          background-color: #fff;
        }

        .accordion {
          width: 100%;
          font-family: "Arial", sans-serif;
        }
        .status-bar {
          padding: 10px;
          background-color: #f5f5f5;
          margin-bottom: 15px;
          box-shadow: 0px 2px 5px rgba(0, 0, 0, 0.1);
          border-radius: 3px;
        }
        .accordion-item {
          margin: 10px 0;
          border-radius: 5px;
          overflow: hidden;
          box-shadow: 0px 3px 8px rgba(0, 0, 0, 0.12);
          transition: box-shadow 0.3s;
        }
        .accordion-item:hover {
          box-shadow: 0px 5px 15px rgba(0, 0, 0, 0.15);
        }
        .accordion-header {
          cursor: pointer;
          padding: 15px 20px;
          background: linear-gradient(120deg, #f6f8fa, #e9ecef);
          transition: background-color 0.3s;
        }
        .accordion-header:hover {
          background-color: #e2e2e2;
        }
        .accordion-content {
          padding: 15px 20px;
          background-color: #ffffff;
        }
        input {
          width: 100%;
          padding: 8px 12px;
          margin: 5px 0;
          border: 1px solid #d1d1d1;
          border-radius: 4px;
          font-size: 16px;
          transition: border-color 0.3s;
          outline: none; // To remove the default browser outline
        }
        input:hover,
        input:focus {
          border-color: #a1a1a1;
        }

        button {
          margin-top: 15px;
          padding: 8px 20px;
          background-color: #007bff;
          color: #ffffff;
          border: none;
          border-radius: 3px;
          box-shadow: 0px 2px 5px rgba(0, 0, 0, 0.1);
          cursor: pointer;
          transition: background-color 0.3s, transform 0.1s;
        }
        button:hover {
          background-color: #0056b3;
        }
        button:active {
          transform: scale(0.98);
        }
      `}</style>
    </div>
  );
};

export default Questionnaire;
